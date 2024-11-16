from datetime import date, datetime, timedelta
from prettytable import PrettyTable, HRuleStyle as PrettyTableHorizontalStyle
import sys
from typing import Optional, Tuple
from dcicutils.datetime_utils import format_time
from dcicutils.misc_utils import format_size
from hms_utils.argv import ARGV
from hms_utils.datetime_utils import format_date, parse_datetime_string
from hms_utils.dictionary_utils import get_property
from hms_utils.portal.portal_utils import Portal
from hms_utils.type_utils import to_non_empty_string_list


def main():

    argv = ARGV({
        ARGV.OPTIONAL(str, "smaht-data"): ["--env"],
        ARGV.OPTIONAL(str): ["--app"],
        ARGV.OPTIONAL(bool): ["--all"],
        ARGV.OPTIONAL(str): ["--from-date", "--from"],
        ARGV.OPTIONAL(str): ["--thru-date", "--thru", "--to"],
        ARGV.OPTIONAL(int): ["--limit", "--count"],
        ARGV.OPTIONAL(int): ["--offset", "--skip"],
        ARGV.OPTIONAL(str): ["--status", "--state"],
        ARGV.OPTIONAL(str): ["--sort"],
        ARGV.OPTIONAL(bool): "--verbose",
        ARGV.OPTIONAL(bool): ["--nowarnings", "--nowarning", "--nowarn"],
        ARGV.OPTIONAL(bool): "--debug",
        ARGV.OPTIONAL(bool): "--ping"
    })

    _setup_debugging(argv)

    if not (portal := Portal.create(argv.env, app=argv.app, verbose=argv.verbose, debug=argv.debug, ping=argv.ping)):
        return 1

    from_date, thru_date = _parse_from_and_thru_date_args(argv) if not argv.all else (None, None)

    date_property_name = "file_status_tracking.released"
    if status := argv.status:
        if (status := status.lower()) == "released":
            date_property_name = "file_status_tracking.released"
        elif status == "public":
            date_property_name = "file_status_tracking.public"
        elif status == "restricted":
            date_property_name = "file_status_tracking.restricted"
        elif status == "uploading":
            date_property_name = "file_status_tracking.uploading"
        elif status == "uploaded":
            date_property_name = "file_status_tracking.uploaded"
        else:
            _error(f"Invalid status specified: {argv.status}")

    # FYI: Note that using a portal query like this (using just date no time):
    #
    # - file_status_tracking.released.from=2024-11-01&file_status_tracking.released.to=2024-11-30
    #
    # results in an OpenSearch range query predicate like this:
    #
    # - {"embedded.file_status_tracking.released": {
    #    "format": "yyyy-MM-dd HH:mm", "gte": "2024-11-01 00:00", "lte": "2024-11-30 23:59"}}
    #
    # i.e. so adding 23:59 to mark the and of the day of the upper bound is properly handled by portal.

    query = "&".join(to_non_empty_string_list([
        f"/files",
        f"limit=1000",
        f"sort=file_status_tracking.released",
        f"status={status}" if status else None,
        f"file_status_tracking.{date_property_name}.from={from_date}" if from_date else None,
        f"file_status_tracking.{date_property_name}.to={thru_date}" if thru_date else None,
    ])).replace("&", "?", 1)

    if argv.debug:
        _debug(f"Executing portal query: {query}")

    if not (items := portal.get_metadata(query, raise_exception=False)):
        return 1

    if not isinstance(items := items.get("@graph"), list):
        _error(f"Query did not return a list as expected: {query}")

    _verbose(f"Number of files retrieved: {len(items)}")

    # Example record:
    # {
    #     "software": [
    #         "f349ceba-ac73-4332-b9cb-5cd3b4598d60"
    #     ],
    #     "s3_lifecycle_status": "standard",
    #     "access_status": "Open",
    #     "description": "Extremely-difficult-to-map regions: Regions outside of the easy- or difficult-to-map regions",
    #     "accession": "SMASFP5V44A8",
    #     "uuid": "4a86ba8c-b442-41c2-ab93-516736b98322",
    #     "schema_version": "1",
    #     "reference_genome": "e89937e6-80d3-4605-8dea-4a74c7981a9f",
    #     "md5sum": "7fe0cac3336dc161d315121fde5355fe",
    #     "submission_centers": [
    #         "9626d82e-8110-4213-ac75-0a50adf890ff"
    #     ],
    #     "last_modified": {
    #         "date_modified": "2024-11-01T13:42:31.228341+00:00",
    #         "modified_by": "74fef71a-dfc1-4aa4-acc0-cedcb7ac1d68"
    #     },
    #     "file_format": "4c04f6de-89a7-4477-8dc4-811b50c67401",
    #     "date_created": "2024-08-12T18:12:42.110604+00:00",
    #     "submitted_by": "5519933a-7772-4188-a318-afc84c1302cd",
    #     "data_category": [
    #         "Genome Region"
    #     ],
    #     "content_md5sum": "7fe0cac3336dc161d315121fde5355fe",
    #     "version": "1.0",
    #     "consortia": [
    #         "358aed10-9b9d-4e26-ab84-4bd162da182b"
    #     ],
    #     "submitted_id": "DAC_SUPPLEMENTARY-FILE_GRCH38-EXTREME-REGIONS",
    #     "file_size": 5886352,
    #     "tags": [
    #         "genome_stratification"
    #     ],
    #     "filename": "SMaHT_extreme_regions_GRCh38_v1.0.bed",
    #     "data_type": [
    #         "Sequence Interval"
    #     ],
    #     "dataset": "colo829_snv_indel_challenge_data",
    #     "status": "released"
    # }

    table = PrettyTable()
    table.field_names = ["FILE", "TYPE / SIZE", "STATUS", "DATE"]
    table.align = "l"
    # table.align["SIZE"] = "r"
    if argv.verbose:
        table.hrules = PrettyTableHorizontalStyle.ALL

    for item in items:

        uuid = item.get("uuid", "")
        type = portal.get_item_type(item)
        status = item.get("status", "")
        description = item.get("description", "")
        name = item.get("filename", item.get("display_title", ""))
        size = item.get("file_size", "")
        date = get_property(item, date_property_name, get_property(item, "last_modified.date_modified"))
        by = get_property(item, "submitted_by.display_title",
                                get_property(item, "last_modified.modified_by.display_title"))

        type_and_size = f"{type}\n{format_size(size)}"

        if argv.verbose:
            name += f"\n{uuid}"
            name += f"\n{description}"
            date = f"{format_date(date)}\n{format_time(date, notz=True)}"
            if by:
                date += f"\n{by}"
        else:
            date = f"{format_date(date)}"

        table.add_row([
            name,
            type_and_size,
            status,
            date
        ])

    print(table)


def _parse_from_and_thru_date_args(argv: ARGV) -> Tuple[Optional[str], Optional[str]]:
    from_date = thru_date = None
    if not (argv.from_date and argv.thru_date):
        from_date, thru_date = _get_first_and_last_date_of_month()
    if argv.from_date:
        if not (from_date := parse_datetime_string(argv.from_date)):
            _error(f"Cannot parse given from date: {argv.from_date}")
    if argv.thru_date:
        if not (thru_date := parse_datetime_string(argv.thru_date)):
            _error(f"Cannot parse given thru date: {argv.thru_date}")
    return format_date(from_date), format_date(thru_date)


def _get_first_and_last_date_of_month(today: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    if not isinstance(today, datetime):
        today = date.today()
    first_day = today.replace(day=1)
    next_month = first_day.replace(month=first_day.month % 12 + 1, day=1)
    last_day = next_month - timedelta(days=1)
    return (first_day, last_day)


def _print(*args, **kwargs) -> None:
    print(*args, **kwargs)


def _verbose(*args, **kwargs) -> None:
    _print(*args, **kwargs, file=sys.stderr, flush=True)


def _debug(message: str) -> None:
    _print(f"DEBUG: {message}", file=sys.stderr, flush=True)


def _error(message: str, exit: bool = True) -> None:
    print(f"ERROR: {message}", file=sys.stderr, flush=True)
    if exit is not False:
        sys.exit(1)


def _setup_debugging(argv: ARGV) -> None:
    global _verbose, _debug
    if argv.nowarnings: _warning = lambda *args, **kwargs: None  # noqa
    if not argv.verbose: _verbose = lambda *args, **kwargs: None  # noqa
    if not argv.debug: _debug = lambda *args, **kwargs: None  # noqa


if __name__ == "__main__":
    status = main()
    sys.exit(status if isinstance(status, int) else 0)
