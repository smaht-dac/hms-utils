# On 2024-10-31 it was noticed that smaht-submitr had not been setting consortia for items submitted to smaht-portal.
# This bug has been fixed (C4-1186) and this script (C4-1187) is to correct the existing data.
# Before this was run a backup was made of the smaht-portal (RDS) database: rds-smaht-production-snapshot-20241031

from typing import List
from dcicutils.ff_utils import search_metadata
from hms_utils.portal.portal_utils import Portal
from hms_utils.argv import ARGV
from hms_utils.chars import chars
from hms_utils.threading_utils import run_concurrently

nerrors = 0
total = 0


def main():

    argv = ARGV({
        ARGV.REQUIRED(str, "smaht-data"): ["--env"],
        ARGV.OPTIONAL(bool): ["--dryrun"],
        # Running into Internal Server Error on some Library types - this "fixes" it
        ARGV.OPTIONAL(bool, True): ["--skip-links"],
        ARGV.OPTIONAL(int, 0): ["--limit"]
    })

    portal = Portal(argv.env)

    query = "/search/?type=Item&consortia.display_title=No+value"
    ignored_types = ["AccessKey", "TrackingItem", "Consortium", "SubmissionCenter"]
    results = search_metadata(query, key=portal.key, is_generator=True)
    consortia = ["smaht"]

    print(f"SETTING CONSORTIA FOR PORTAL ITEMS WITHOUT IT: {portal.server}")
    if argv.dryrun:
        print(f"{chars.rarrow}{chars.rarrow}{chars.rarrow} DRY RUN {chars.larrow}{chars.larrow}{chars.larrow}")
    concurrency = 50
    functions = []
    nitems = 0
    for item in results:
        if isinstance(item, dict) and (item_uuid := item.get("uuid")):
            if (item_type := portal.get_schema_type(item)) not in ignored_types:
                if item.get("consortia", None) is None:
                    if (argv.limit > 0) and (nitems >= argv.limit):
                        print(f"REACHED LIMIT: {argv.limit}")
                        break
                    nitems += 1
                    print(f"{item_uuid}: {item_type} {chars.rarrow_hollow} SETTING CONSORTIA: {consortia}", flush=True)
                    if not argv.dryrun:
                        functions.append(lambda portal=portal, item=item, consortia=consortia:
                                         _set_consortia(portal, item, consortia, skip_links=argv.skip_links))
                        if len(functions) >= concurrency:
                            run_concurrently(functions, nthreads=concurrency)
                            functions = []
                else:
                    print(f"{item_uuid}: {item_type} {chars.rarrow_hollow} CONSORTIA ALREADY SET")

    if functions:
        run_concurrently(functions, nthreads=concurrency)

    global total, nerrors
    if argv.dryrun:
        print(f"DONE REVIEWING PORTAL ITEMS WITHOUT CONSORTIA:"
              f" {portal.server} {chars.dot} total: {nitems} {chars.dot} errors: {nerrors}")
        print(f"{chars.rarrow}{chars.rarrow}{chars.rarrow} DRY RUN {chars.larrow}{chars.larrow}{chars.larrow}")
    else:
        print(f"DONE SETTING CONSORTIA FOR PORTAL ITEMS WITHOUT IT:"
              f" {portal.server} {chars.dot} total: {total} {chars.dot} errors: {nerrors}")


def _set_consortia(portal: Portal, item: dict, consortia: List[str], skip_links: bool = False) -> None:
    global total, nerrors
    try:
        item_uuid = item.get("uuid")
        item_type = portal.get_schema_type(item)
        print(f"{item_uuid}: {item_type} {chars.rarrow_hollow} SETTING CONSORTIA: {consortia}", flush=True)
        if skip_links:
            item_uuid += "?skip_links=true"
        portal.patch_metadata(item_uuid, {"consortia": consortia})
        total += 1
    except Exception as e:
        nerrors += 1
        print(e, flush=True)


if __name__ == "__main__":
    main()
    pass
