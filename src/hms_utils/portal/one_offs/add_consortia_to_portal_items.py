# On 2024-10-31 it was noticed that smaht-submitr had not been setting consortia for items submitted to smaht-portal.
# This bug has been fixed (C4-1186) and this script (C4-1187) is to correct the existing data.
# Before this was run a backup was made of the smaht-portal (RDS) database: rds-smaht-production-snapshot-20241031

import sys
import time
from dcicutils.ff_utils import search_metadata
from hms_utils.portal.portal_utils import Portal
from hms_utils.chars import chars

portal_env = "smaht-data"
portal_env = "smaht-devtest"
portal_env = "smaht-wolf"
portal = Portal(portal_env)


query = "/search/?type=Item&consortia.display_title=No+value"
# query = "/search/?type=Item&consortia.display_title=No+value&uuid=57eda24e-a254-46ae-9b23-484a4d24728a"
ignored_types = ["AccessKey", "TrackingItem", "Consortium", "SubmissionCenter"]
results = search_metadata(query, key=portal.key, is_generator=True)
consortia = ["smaht"]

for item in results:
    if isinstance(item, dict) and (item_uuid := item.get("uuid")):
        if (item_type := portal.get_schema_type(item)) not in ignored_types:
            if (existing_consortia := item.get("consortia", None)) is None:
                print(f"{item_uuid}: {item_type} {chars.rarrow_hollow} SETTING CONSORTIA: {consortia}")
                try:
                    portal.patch_metadata(item_uuid, {"consortia": consortia})
                except Exception:
                    print(f"ERROR: Cannot patch {item_uuid}. Trying reindex of this item.", file=sys.stderr, flush=True)
                    if not portal.reindex_metadata(item_uuid):
                        print(f"ERROR: Reindex failed: {item_uuid}", file=sys.stderr, flush=True)
                    else:
                        time.sleep(2)
                        print(f"Trying patch again: {item_uuid}", file=sys.stderr, flush=True)
                        portal.patch_metadata(item_uuid, {"consortia": consortia})
            else:
                print(f"{item_uuid}: {item_type} {chars.rarrow_hollow} CONSORTIA ALREADY SET")
