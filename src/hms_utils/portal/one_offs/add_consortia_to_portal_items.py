# On 2024-10-31 it was noticed that smaht-submitr had not been setting consortia for items submitted to smaht-portal.
# This bug has been fixed (C4-1186) and this script (C4-1187) is to correct the existing data.
# Before this was run a backup was made of the smaht-portal (RDS) database: rds-smaht-production-snapshot-20241031

import sys
import time
from dcicutils.ff_utils import search_metadata
from dcicutils.portal_utils import Portal
from hms_utils.type_utils import is_uuid

portal_env = "smaht-data"
portal_env = "smaht-devtest"
portal_env = "smaht-wolf"
portal = Portal(portal_env)


def reindex_item(uuid: str) -> bool:
    if is_uuid(uuid):
        uuids = [uuid]
        query_indexing_post_data = {"uuids": uuids}
        print(f"DEBUG: Reindexing item: {item_uuid}", file=sys.stderr, flush=True)
        import pdb ; pdb.set_trace()  # noqa
        pass
        response = portal.post("/queue_indexing", json=query_indexing_post_data)
        print(f"DEBUG: Done reindexing item: {item_uuid}", file=sys.stderr, flush=True)
        return response.status_code == 200


query = "/search/?type=Item&consortia.display_title=No+value"
# query = "/search/?type=Item&consortia.display_title=No+value&uuid=57eda24e-a254-46ae-9b23-484a4d24728a"
ignored_types = ["AccessKey", "TrackingItem", "Consortium", "SubmissionCenter"]
results = search_metadata(query, key=portal.key, is_generator=True)
consortia = ["smaht"]

for item in results:
    if isinstance(item, dict) and (item_uuid := item.get("uuid")):
        if (item_type := portal.get_schema_type(item)) not in ignored_types:
            if (existing_consortia := item.get("consortia", None)) is None:
                print(f"{item_uuid}: {item_type} -> SETTING CONSORTIA TO {consortia}")
                try:
                    portal.patch_metadata(item_uuid, {"consortia": consortia})
                except Exception as e:
                    print(f"ERROR: Cannot patch {item_uuid}", file=sys.stderr, flush=True)
                    reindex_item(item_uuid)
                    time.sleep(7)
                    print(f"DEBUG: Trying patch again {item_uuid}", file=sys.stderr, flush=True)
                    portal.patch_metadata(item_uuid, {"consortia": consortia})
                    print(f"DEBUG: Done trying patch again {item_uuid}", file=sys.stderr, flush=True)
                    print(str(e), file=sys.stderr, flush=True)
            else:
                print(f"{item_uuid}: {item_type} -> CONSORTIA ALREADY EXISTS")
