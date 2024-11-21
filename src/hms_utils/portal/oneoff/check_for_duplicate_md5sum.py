import io
import json
import os

# hms-portal-read --env fourfront-data /files-processed --limit 1000 --inserts --output exported-from-fourfront-data-files-processed-limit-1000-20241121.json  # noqa
file = os.path.expanduser("exported-from-fourfront-data-files-processed-limit-1000-20241121.json")
file = os.path.expanduser("exported-from-fourfront-data-files-processed-limit-10000-20241121.json")
file = os.path.expanduser("~/repos/etc/repo-extras/portal/4dn/data/exported-from-fourfront-data-experiment-set-replicates-4DNESXP5VE8C-20241120-3-noignore-static-content/file_processed.json")  # noqa
md5sums = {}
md5sums_duplicates = {}
with io.open(file, "r") as f:
    items = json.load(f)
    if isinstance(items, list):
        items = {"Dummy": items}
    for item_type in items:
        for item in items[item_type]:
            if md5sum := item.get("md5sum"):
                item_uuid = item.get("uuid")
                if md5sum_uuids := md5sums.get(md5sum):
                    print(f"DUPLICATE MD5: {md5sum} | uuid: {item_uuid} | {md5sum_uuids}")
                    md5sum_uuids.append(item_uuid)
                    md5sums_duplicates[md5sum] = md5sum_uuids
                else:
                    md5sums[md5sum] = [item_uuid]
print(f"TOTAL DUPLICATE MD5: {len(md5sums_duplicates)}")
