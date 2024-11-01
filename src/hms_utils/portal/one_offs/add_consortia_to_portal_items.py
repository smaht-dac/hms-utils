# On 2024-10-31 it was noticed that smaht-submitr had not been setting consortia for items submitted to smaht-portal.
# This bug has been fixed (C4-1186) and this script (C4-1187) is to correct the existing data.
# Before this was run a backup was made of the smaht-portal (RDS) database: rds-smaht-production-snapshot-20241031

from dcicutils.ff_utils import search_metadata
from hms_utils.portal.portal_utils import Portal
from hms_utils.chars import chars
from hms_utils.threading_utils import run_concurrently

portal_env = "smaht-devtest"
portal_env = "smaht-wolf"
portal_env = "smaht-staging"
portal_env = "smaht-local"
portal = Portal(portal_env)


query = "/search/?type=Item&consortia.display_title=No+value&uuid=154b3865-3b21-410a-88b9-548ccdc5b2e2"
ignored_types = ["AccessKey", "TrackingItem", "Consortium", "SubmissionCenter"]
results = search_metadata(query, key=portal.key, is_generator=True)
consortia = ["smaht"]
nerrors = 0
total = 0


def set_consortia(item: dict) -> None:
    global consortia, total, nerrors
    try:
        item_uuid = item.get("uuid")
        item_type = portal.get_schema_type(item)
        print(f"{item_uuid}: {item_type} {chars.rarrow_hollow} SETTING CONSORTIA: {consortia}", flush=True)
        portal.patch_metadata(item_uuid, {"consortia": consortia})
        total += 1
    except Exception as e:
        nerrors += 1
        print(e, flush=True)


print(f"SETTING CONSORTIA FOR PORTAL ITEMS WITHOUT: {portal.server}")
concurrency = 50
functions = []
for item in results:
    if isinstance(item, dict) and (item_uuid := item.get("uuid")):
        if (item_type := portal.get_schema_type(item)) not in ignored_types:
            if (existing_consortia := item.get("consortia", None)) is None:
                print(f"{item_uuid}: {item_type} {chars.rarrow_hollow} SETTING CONSORTIA: {consortia}", flush=True)
                if True:
                    functions.append(lambda item=item: set_consortia(item))
                    if len(functions) >= concurrency:
                        run_concurrently(functions, nthreads=concurrency)
                        functions = []
            else:
                print(f"{item_uuid}: {item_type} {chars.rarrow_hollow} CONSORTIA ALREADY SET")


if functions:
    run_concurrently(functions, nthreads=concurrency)

print(f"DONE SETTING CONSORTIA FOR PORTAL ITEMS WITHOUT:"
      f"{portal.server} {chars.rarrow_hollow} {total} (errors: {nerrors})")
