import calendar
from copy import deepcopy
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import pyramid
from typing import Any, Callable, List, Optional, Tuple, Union
from urllib.parse import urlencode
from dcicutils.datetime_utils import parse_datetime_string
from encoded.root import SMAHTRoot

from snovault.search.search import search as snovault_search
from snovault.search.search_utils import make_search_subreq as snovault_make_search_subreq

from hms_utils.elasticsearch_utils import merge_elasticsearch_aggregation_results, normalize_elasticsearch_aggregation_results
from hms_utils.elasticsearch_utils import normalize_elasticsearch_aggregation_results_legacy

def dj(value):
    import json
    print(json.dumps(value, indent=4, default=str))


AGGREGATION_FIELD_RELEASE_DATE = "file_status_tracking.released"
AGGREGATION_FIELD_RELEASE_DATE = "date_created"
AGGREGATION_FIELD_CELL_LINE = "file_sets.libraries.analytes.samples.sample_sources.cell_line.code"
AGGREGATION_FIELD_DONOR = "donors.display_title"
AGGREGATION_FIELD_FILE_DESCRIPTOR = "release_tracker_description"

AGGREGATIONS = [
    AGGREGATION_FIELD_RELEASE_DATE,
    AGGREGATION_FIELD_CELL_LINE,
    AGGREGATION_FIELD_DONOR,
    AGGREGATION_FIELD_FILE_DESCRIPTOR
]

AGGREGATIONS_BY_CELL_LINE = [
    AGGREGATION_FIELD_RELEASE_DATE,
    AGGREGATION_FIELD_CELL_LINE,
    AGGREGATION_FIELD_FILE_DESCRIPTOR
]

AGGREGATIONS_BY_DONOR = [
    AGGREGATION_FIELD_RELEASE_DATE,
    AGGREGATION_FIELD_DONOR,
    AGGREGATION_FIELD_FILE_DESCRIPTOR
]

AGGREGATION_MAX_BUCKETS = 100
AGGREGATION_NO_VALUE = "No value"

DEFAULT_FILE_TYPES = ["OutputFile"]
DEFAULT_FILE_STATUSES = ["released"]
DEFAULT_FILE_CATEGORIES = ["!Quality Control"]
DEFAULT_RECENT_MONTHS = 3
DEFAULT_INCLUDE_CURRENT_MONTH = True


def recent_files_summary(context: SMAHTRoot, request: pyramid.request.Request) -> dict:

    def create_query(request: pyramid.request.Request) -> str:

        global AGGREGATION_FIELD_RELEASE_DATE, DEFAULT_FILE_CATEGORIES, DEFAULT_FILE_STATUSES, DEFAULT_FILE_TYPES

        types = request_args(request, "type", DEFAULT_FILE_TYPES)
        statuses = request_args(request, "status", DEFAULT_FILE_STATUSES)
        categories = request_args(request, "category", DEFAULT_FILE_CATEGORIES)
        from_date = request_arg(request, "from")
        thru_date = request_arg(request, "thru")
        nmonths = request_arg_int(request, "months", DEFAULT_RECENT_MONTHS)
        include_current_month = request_arg_bool(request, "include_current_month")
        date_property_name = request_arg(request, "date_property_name", AGGREGATION_FIELD_RELEASE_DATE)
        # Nevermind on this because it will filter out EITHER files without donor OR cell-line, i.e. only query FOR files with BOTH
        # which we definitely do not want; in fact normally a file will have one or the other but not both..
        # ignore_ungrouped = request_arg(request, "ignore_ungrouped", True)

        from_date, thru_date = parse_date_related_arguments(from_date, thru_date, nmonths=nmonths,
                                                            include_current_month=include_current_month, strings=True)
        query_parameters = {
            "type": types if types else None,
            "status": statuses if statuses else None,
            "data_category": categories if categories else None,
            f"{date_property_name}.from": from_date if from_date else None,
            f"{date_property_name}.to": thru_date if from_date else None,
            # f"{AGGREGATION_FIELD_CELL_LINE}": f"!{AGGREGATION_NO_VALUE}" if ignore_ungrouped else None,
            # f"{AGGREGATION_FIELD_DONOR}": f"!{AGGREGATION_NO_VALUE}" if ignore_ungrouped else None,
            "from": 0,
            "limit": 0,

        }
        query_parameters = {key: value for key, value in query_parameters.items() if value is not None}
        query_string = urlencode(query_parameters, True)
        # Hackishness to change "=!" to "!=" in search_param_lists value for e.g.: "data_category": ["!Quality Control"]
        query_string = query_string.replace("=%21", "%21=")
        return query_string

    def create_elasticsearch_aggregation_query(groupings: List[str]) -> dict:
        global AGGREGATION_FIELD_RELEASE_DATE, AGGREGATION_MAX_BUCKETS, AGGREGATION_NO_VALUE
        aggregations = []
        if not isinstance(groupings, list):
            groupings = [groupings]
        for item in groupings:
            if isinstance(item, str) and (item := item.strip()) and (item not in aggregations):
                aggregations.append(item)
        if not aggregations:
            return {}
        def create_field_aggregation(field: str) -> Optional[dict]:  # noqa
            global AGGREGATION_FIELD_RELEASE_DATE
            if field == AGGREGATION_FIELD_RELEASE_DATE:
                return {
                    "date_histogram": {
                        "field": f"embedded.{field}",
                        "calendar_interval": "month",
                        "format": "yyyy-MM",
                        "missing": "1970-01",
                        "order": {"_key": "desc"}
                    }
                }
        aggregation = _create_elasticsearch_aggregation_query(
            aggregations,
            aggregation_property_name="TODO_GET_RID_OF_THIS",
            max_buckets=AGGREGATION_MAX_BUCKETS,
            missing_value=AGGREGATION_NO_VALUE,
            create_field_aggregation=create_field_aggregation)
        return aggregation["TODO_GET_RID_OF_THIS"]

    def execute_query(request: pyramid.request.Request, query: str, aggregations: dict) -> str:
        request = snovault_make_search_subreq(request, path=query, method="GET")
        return snovault_search(None, request, custom_aggregations=aggregations)

    query = f"/search/?{create_query(request)}"
    aggregations = {
        "group_by_cell_line": create_elasticsearch_aggregation_query(AGGREGATIONS_BY_CELL_LINE),
        "group_by_donor": create_elasticsearch_aggregation_query(AGGREGATIONS_BY_DONOR)
    }

    print("QUERY:")
    print(query)
    print("AGGREGATION QUERY:")
    dj(aggregations)
    results = execute_query(request, query, aggregations)
    # print("RAW RESULTS:")
    # dj(results)

    if aggregation_results := results.get("aggregations"):
        results_by_cell_line = aggregation_results.get("group_by_cell_line")
        print("RAW CELL-LINE RESULTS:")
        dj(results_by_cell_line)
        results_by_donor = aggregation_results.get("group_by_donor")
        print("RAW DONOR RESULTS:")
        dj(results_by_donor)
        results = merge_elasticsearch_aggregation_results(results_by_cell_line, results_by_donor)
        print("MERGED RESULTS:")
        dj(results)
        #
        # Note that the doc_count values returned by ElasticSearch do actually seem to be for unique items,
        # i.e. if an item appears in two different groups (e.g. if, say, f2584000-f810-44b6-8eb7-855298c58eb3
        # has file_sets.libraries.analytes.samples.sample_sources.cell_line.code values for both HG00438 and HG005),
        # then it its doc_count will not count it twice. This creates a situation where it might look like the counts
        # are wrong in this returned merged/normalized result set where the outer item count is less than the sum of
        # the individual counts withni each sub-group. For example, the below result shows a top-level doc_count of 1
        # even though there are 2 documents, 1 in the HG00438 group and the other in the HG005 it would be because
        # the same unique file has a cell_line.code of both HG00438 and HG005.
        # {
        #     "meta": { "field_name": "file_status_tracking.released" },
        #     "buckets": [
        #         {
        #             "key_as_string": "2024-12", "key": 1733011200000, "doc_count": 1,
        #             "file_sets.libraries.analytes.samples.sample_sources.cell_line.code": {
        #                 "meta": { "field_name": "file_sets.libraries.analytes.samples.sample_sources.cell_line.code" },
        #                 "buckets": [
        #                     {   "key": "HG00438", "doc_count": 1,
        #                         "release_tracker_description": {
        #                             "meta": { "field_name": "release_tracker_description" },
        #                             "buckets": [
        #                                 { "key": "WGS Illumina NovaSeq X bam", "doc_count": 1 },
        #                             ]
        #                         }
        #                     },
        #                     {   "key": "HG005", "doc_count": 1,
        #                         "release_tracker_description": {
        #                             "meta": { "field_name": "release_tracker_description" },
        #                             "buckets": [
        #                                 { "key": "Fiber-seq PacBio Revio bam", "doc_count": 1 }
        #                             ]
        #                         }
        #                     }
        #                 ]
        #             }
        #         }
        #     ]
        # }
        #
        return normalize_elasticsearch_aggregation_results(results)

#   results_by_cell_line = results["aggregations"]["group_by_cell_line"]
#   results_by_donor = results["aggregations"]["group_by_donor"]
#   results_merged = merge_elasticsearch_aggregation_results(results_by_cell_line, results_by_donor, copy=True)
#   print("MERGED RESULTS:")
#   dj(results_merged)
#   print("NORMALIZED RESULTS:")
#   results_normalized = normalize_elasticsearch_aggregation_results(results_merged)
#   dj(results_normalized)

#   return results_normalized

    # results_by_cell_line = normalize_elasticsearch_aggregation_results(results_group_by_cell_line)

    # results_by_cell_line = normalize_elasticsearch_aggregation_results(results_group_by_cell_line)
    # results_by_donor = normalize_elasticsearch_aggregation_results(results_group_by_donor)

    # print("RESULTS BY CELL-LINE (NORMALIZED):")
    # dj(results_by_cell_line)

    # print("RESULTS BY DONOR (NORMALIZED):")
    # dj(results_by_donor)

    # from hms_utils.dictionary_print_utils import print_grouped_items  # noqa
    # print_grouped_items(results_normalized)


def _create_elasticsearch_aggregation_query(fields: List[str],
                                            aggregation_property_name: Optional[str] = None,
                                            max_buckets: Optional[int] = None,
                                            missing_value: Optional[str] = None,
                                            create_field_aggregation: Optional[Callable] = None) -> dict:

    global AGGREGATION_MAX_BUCKETS, AGGREGATION_NO_VALUE

    if not (isinstance(fields, list) and fields and isinstance(field := fields[0], str) and field):
        return {}
    if not isinstance(missing_value, str):
        missing_value = AGGREGATION_NO_VALUE
    if not (isinstance(max_buckets, int) and (max_buckets > 0)):
        max_buckets = AGGREGATION_MAX_BUCKETS

    if not (callable(create_field_aggregation) and
            isinstance(field_aggregation := create_field_aggregation(field), dict)):
        field_aggregation = {
            "terms": {
                "field": f"embedded.{field}.raw",
                "missing": missing_value,
                "size": max_buckets
            }
        }

    if not (isinstance(aggregation_property_name, str) and
            (aggregation_property_name := aggregation_property_name.strip())):
        aggregation_property_name = field
    aggregation = {aggregation_property_name: field_aggregation}
    aggregation[aggregation_property_name]["meta"] = {"field_name": field}

    if nested_aggregation := _create_elasticsearch_aggregation_query(
            fields[1:], max_buckets=max_buckets,
            missing_value=missing_value,
            create_field_aggregation=create_field_aggregation):
        aggregation[aggregation_property_name]["aggs"] = nested_aggregation

    return aggregation


def request_arg(request: pyramid.request.Request, name: str, fallback: Optional[str] = None) -> Optional[str]:
    return str(value).strip() if (value := request.params.get(name, None)) is not None else fallback


def request_arg_int(request: pyramid.request.Request, name: str, fallback: Optional[int] = 0) -> Optional[Any]:
    if (value := request_arg(request, name)) is not None:
        try:
            return int(value)
        except Exception:
            pass
    return fallback


def request_arg_bool(request: pyramid.request.Request, name: str, fallback: Optional[bool] = False) -> Optional[bool]:
    return fallback if (value := request_arg(request, name)) is None else (value.lower() == "true")


def request_args(request: pyramid.request.Request,
                 name: str, fallback: Optional[str] = None, duplicates: bool = False) -> List[str]:
    args = []
    if isinstance(value := request.params.getall(name), list):
        for item in value:
            if isinstance(item, str) and (item := item.strip()):
                if (item not in args) or (duplicates is True):
                    args.append(item)
    return args if args else fallback


def parse_date_related_arguments(
        from_date: Optional[Union[str, datetime, date]],
        thru_date: Optional[Union[str, datetime, date]],
        nmonths: Optional[Union[str, int]] = None,
        include_current_month: bool = True,
        strings: bool = False) -> Tuple[Optional[Union[str, datetime]], Optional[Union[str, datetime]]]:

    """
    Returns from/thru dates based on the given from/thru date arguments and optional nmonths argument.
    Given dates may be datetime or date objects or strings. Returned dates are datetime objects, or
    if the the given strings arguments is True, then strings (formatted as YYYY-MM-DD).

    If both of the given from/thru dates are specified/valid then those are returned
    and the given nmonths argument is not used.

    If only the given from date is specified then a None thru date is returned, UNLESS the given nmonths
    argument represents a positive integer, in which case the returned thru date will be nmonths months
    subsequent to the given from date; or if the given nmonths represents zero, in which case the
    returned thru date will be the last date of the month of the given from date.

    If only the given thru date is specified then a None from date is returned, UNLESS the given nmonths
    argument represents a negative integer, in which case the returned from date will be nmonths monthss
    previous to the given thru date; or if the given nmonths represents zero, in which case
    the returned from date will be the first date of the month of the given thru date.

    If neither the given from/thru dates are specified then None is returns for both, UNLESS the given
    nmonths arguments represents a non-zero integer, in which case the returned from/thru dates will represent
    the past (absolute value) nmonths months starting with the month previous to the month of "today"; however
    if the include_current_month is True it is rather the past nmonths starting with the month of "today".
    """
    from_date = _parse_datetime_string(from_date, notz=True)
    thru_date = _parse_datetime_string(thru_date, last_day_of_month_if_no_day=True, notz=True)
    if not isinstance(nmonths, int):
        if isinstance(nmonths, str) and (nmonths := nmonths.strip()):
            try:
                nmonths = int(nmonths)
            except Exception:
                nmonths = 0
        else:
            nmonths = 0
    if from_date:
        if (not thru_date) and isinstance(nmonths, int):
            if nmonths > 0:
                thru_date = add_months(from_date, nmonths)
            elif nmonths == 0:
                thru_date = get_last_date_of_month(from_date)
    elif thru_date:
        if isinstance(nmonths, int):
            if nmonths < 0:
                from_date = add_months(thru_date, nmonths)
            elif nmonths == 0:
                from_date = get_first_date_of_month(thru_date)
    elif isinstance(nmonths, int) and ((nmonths := abs(nmonths)) != 0):
        # If no (valid) from/thru dates given, but the absolute value of nmonths is a non-zero integer, then returns
        # from/thru dates for the last nmonths month ending with the last day of month previous to the current month.
        # thru_date = add_months(get_last_date_of_month(), -1)
        thru_date = get_last_date_of_month()
        if include_current_month is not True:
            thru_date = add_months(thru_date, -1)
        from_date = add_months(thru_date, -nmonths)
    if strings is True:
        return (from_date.strftime(f"%Y-%m-%d") if from_date else None,
                thru_date.strftime(f"%Y-%m-%d") if thru_date else None)
    return from_date, thru_date


def get_first_date_of_month(day: Optional[Union[datetime, date, str]] = None) -> datetime:
    """
    Returns a datetime object representing the first day of the month of the given date;
    this given date may be a datetime or date object, or string representing a date or
    datetime; if the given argument is unspecified or incorrect then assumes "today".
    """
    if not (day := _parse_datetime_string(day, notz=True)):
        day = datetime.today().replace(tzinfo=None)
    return day.replace(day=1)


def get_last_date_of_month(day: Optional[Union[datetime, date, str]] = None) -> datetime:
    """
    Returns a datetime object representing the last day of the month of the given date;
    this given date may be a datetime or date object, or string representing a date or
    datetime; if the given argument is unspecified or incorrect then assumes "today".
    """
    if not (day := _parse_datetime_string(day)):
        day = datetime.today().replace(tzinfo=None)
    return datetime(day.year, day.month, calendar.monthrange(day.year, day.month)[1])


def add_months(day: Optional[Union[datetime, date, str]] = None, nmonths: int = 0) -> datetime:
    """
    Returns a datetime object representing the given date with the given nmonths number of months
    added (or substracted if negative) to (or from) that given date.; this given date may be a
    datetime or date object, or string representing a date or datetime; if the given argument
    is unspecified or incorrect then assumes "today".
    """
    if not (day := _parse_datetime_string(day, notz=True)):
        day = datetime.today().replace(tzinfo=None)
    if isinstance(nmonths, int) and (nmonths != 0):
        return day + relativedelta(months=nmonths)
    return day


def _parse_datetime_string(value: Union[str, datetime, date],
                           last_day_of_month_if_no_day: bool = False,
                           notz: bool = False) -> Optional[datetime]:
    """
    Wrapper around dcicutils.datetime_utils.parse_datetime_string to handle a few special cases for convenience.
    """
    last_day_of_month = False
    if not isinstance(value, datetime):
        if isinstance(value, date):
            value = datetime.combine(value, datetime.min.time())
        elif isinstance(value, str):
            if (len(value) == 8) and value.isdigit():
                # Special case to accept for example "20241206" to mean "2024-12-06".
                value = f"{value[0:4]}-{value[4:6]}-{value[6:8]}"
            elif (len(value) == 7) and (value[4] == "-") and value[0:4].isdigit() and value[5:].isdigit():
                # Special case to accept for example "2024-10" to mean "2024-10-01".
                value = f"{value}-01"
                last_day_of_month = last_day_of_month_if_no_day
            elif (len(value) == 7) and (value[2] == "/") and value[0:2].isdigit() and value[3:].isdigit():
                # Special case to accept for example "11/2024" to mean "2024-11-01".
                value = f"{value[3:]}-{value[0:2]}-01"
                last_day_of_month = last_day_of_month_if_no_day
            elif (len(value) == 6) and (value[1] == "/") and value[0:1].isdigit() and value[2:].isdigit():
                # Special case to accept for example "9/2024" to mean "2024-09-01".
                value = f"{value[2:]}-0{value[0:1]}-01"
                last_day_of_month = last_day_of_month_if_no_day
            if not (value := parse_datetime_string(value)):
                return None
        else:
            return None
    value = value.replace(tzinfo=None) if notz is True else value
    if last_day_of_month:
        value = get_last_date_of_month(value)
    return value


import os  # noqa
from urllib.parse import unquote  # noqa
# from hms_utils.dictionary_utils import get_property, group_items_by_groupings, normalize_elasticsearch_aggregation_results as adsfadf  # noqa
from hms_utils.dictionary_print_utils import print_grouped_items  # noqa
from hms_utils.portal.portal_utils import create_pyramid_request_for_testing, portal_custom_search, Portal  # noqa

def test():
    # Arguments to /recent_files_summary endpoint/API.
    request_args = {
        "nmonths": 6,
        "include_current_month": "true"
    }
    # Dummy for local testing.
    portal = Portal(os.path.expanduser("~/repos/smaht-portal/development.ini"))
    request = create_pyramid_request_for_testing(portal.vapp, request_args)
    # Call the /recent_files_summary endpoint/API.
    results = recent_files_summary(None, request)
    # Dump the results.
    print("FINAL RESULTS:")
    dj(results)


test()
