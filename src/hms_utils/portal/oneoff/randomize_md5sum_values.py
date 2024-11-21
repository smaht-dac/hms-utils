import hashlib
import io  # noqa
import json  # noqa
import os
import sys
from typing import List, Union
from uuid import uuid4
from dcicutils.command_utils import yes_or_no


def main():
    if len(sys.argv) > 1:
        file = sys.argv[1]
        randomize_md5sum_values_in_json_file(file, verbose=True)


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


def randomize_md5sum_values_in_json_file(file: str, overwrite: bool = False, verbose: bool = False) -> bool:
    if not os.path.exists(file):
        if verbose:
            print(f"File does not exist: {file}", file=sys.stderr, flush=True)
        return False
    try:
        with io.open(file, "r") as f:
            try:
                if not (data := json.load(f)):
                    print(f"Cannot load JSON from file: {file}", file=sys.stderr, flush=True)
                    return False
                randomize_md5sum_values(data)
            except Exception:
                print(f"Exception loading JSON from file: {file}", file=sys.stderr, flush=True)
                return False
        if overwrite is not True:
            if verbose is not True:
                return False
            if not yes_or_no(f"Overwrite file: {file} ?"):
                return False
        if verbose is True:
            print(f"Overwriting file: {file}")
        try:
            with io.open(file, "w") as f:
                json.dump(data, f, indent=4)
        except Exception:
            print(f"Exception writing file: {file}")
            return False
    except Exception:
        print(f"Cannot open file: {file}")
        return False


if __name__ == "__main__":
    status = main()
    sys.exit(status if isinstance(status, int) else 0)
