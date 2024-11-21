import hashlib
import io  # noqa
import json  # noqa
import os
from typing import List, Optional, Union
from uuid import uuid4
# from dcicutils.command_utils import yes_or_no

file = os.path.expanduser("~/repos/etc/repo-extras/portal/4dn/data/exported-from-fourfront-data-experiment-set-replicates-4DNESXP5VE8C-20241120-3-noignore-static-content/file_processed.json")  # noqa


def randomize_md5sum_values(items: Union[List[dict], dict]) -> None:
    def create_random_md5() -> str:
        return hashlib.md5(str(uuid4()).encode()).hexdigest()
    if isinstance(items, list):
        for element in items:
            randomize_md5sum_values(element)
    elif isinstance(items, dict):
        for key in items:
            if key == "md5sum":
                items[key] = create_random_md5()
            randomize_md5sum_values(items[key])


def randomize_md5sum_values_in_json_file(file: str, overwrite: bool = False) -> Optional[Union[list, dict]]:
    if not os.path.exists(file):
        return None
    try:
        with io.open(file, "r") as f:
            try:
                if not (data := json.load(f)):
                    print(f"Cannot load JSON from file: {file}")
                    return None
                randomize_md5sum_values(data)
                return data
            except Exception:
                print(f"Error loading JSON from file: {file}")
                return None
        if overwrite is True:
            pass
    except Exception:
        print("Cannot open file: {file}")
        return None


data = randomize_md5sum_values_in_json_file(file)
print(json.dumps(data, indent=4))
