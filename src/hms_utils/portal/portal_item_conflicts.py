from __future__ import annotations
from functools import lru_cache
import glob
import io
import json
import os
import sys
from typing import Any, Callable, List, Optional, Union
from dcicutils.portal_utils import Portal as PortalFromUtils
from hms_utils.argv import ARGV
from hms_utils.chars import chars
from hms_utils.dictionary_utils import sort_dictionary
from hms_utils.portal.portal_utils import Portal as Portal
from hms_utils.threading_utils import run_concurrently

_ITEM_UUID_PROPERTY_NAME = "uuid"


def main():

    argv = ARGV({
        ARGV.REQUIRED(str): ["directory"],
        ARGV.OPTIONAL(str): ["--env"],
        ARGV.OPTIONAL(str): ["--app"],
        ARGV.OPTIONAL(int, 32): ["--threads"],
        ARGV.OPTIONAL(bool): ["--ping"],
        ARGV.OPTIONAL(bool, False): ["--verbose"],
        ARGV.OPTIONAL(bool, False): ["--debug"],
    })

    if not os.path.isdir(directory := os.path.expanduser(argv.directory)):
        print(f"Cannot find directory: {directory}")
        return 1

    nitems_total = 0
    nfiles_total = 0

    for file in glob.glob(os.path.join(directory, "*.json")):
        if not Portal.schema_name(file):
            print(f"WARNING: File name does not corresond to known item type name: {file}")
            continue
        try:
            with io.open(file, "r") as f:
                if not isinstance(items := json.load(f), list):
                    print(f"WARNING: File does not contain JSON list: {file}")
                    continue
                nfiles_total += 1
                nitems = len(items)
                nitems_total += nitems
        except Exception:
            print(f"WARNING: Exception loading JSON from file: {file}")
            continue

    if argv.verbose:
        print(f"Checking JSON files in directory for Portal conflicts: {directory}")

    if not (portal := Portal.create(argv.env, app=argv.app, verbose=argv.verbose, debug=argv.debug, ping=argv.ping)):
        print(f"Cannot access Portal: {argv.env}")
        return 1

    if argv.verbose:
        print(f"Total files to check: {nfiles_total}")
        print(f"Total items to check: items: {nitems_total}")
        if argv.threads > 1:
            print(f"Checking concurrency: {argv.threads} threads")

    for file in glob.glob(os.path.join(directory, "*.json")):
        check_file_for_conflicts(portal, file, threads=argv.threads, verbose=argv.verbose, debug=argv.debug)


def check_file_for_conflicts(portal: Portal, file: str,
                             threads: int = 0, verbose: bool = False, debug: bool = False) -> None:

    if not (item_type := Portal.schema_name(file)):
        print(f"WARNING: File name does not corresond to known item type name: {file}")
        return
    try:
        with io.open(file, "r") as f:
            if not isinstance(items := json.load(f), list):
                print(f"WARNING: File does not contain JSON list: {file}")
                return
    except Exception:
        print(f"WARNING: Exception loading JSON from file: {file}")
        return

    def check_item_for_conflicts_function(item: dict) -> None:  # noqa
        nonlocal portal, file, item_type
        check_item_for_conflicts(portal, item=item, item_type=item_type, item_source=file,
                                 report=True, debug=debug)
    if (verbose is True) or (debug is True):
        print(f"Checking file for conflicts: {file}")
    if isinstance(threads, int) and (threads > 0):
        check_item_for_conflicts_functions = []
        for item in items:
            check_item_for_conflicts_functions.append(lambda item=item: check_item_for_conflicts_function(item))
        run_concurrently(check_item_for_conflicts_functions, nthreads=threads)
    else:
        for item in items:
            check_item_for_conflicts(portal, item=item, item_type=item_type, item_source=file,
                                     report=True, debug=debug)


def check_item_for_conflicts(portal: Portal, item: dict, item_type: Optional[str] = None,
                             item_source: Optional[str] = None,
                             report: bool = False, printf: Optional[Callable] = None,
                             debug: bool = False) -> Union[List[dict], bool]:

    def identifying_values_are_equal(item_identifying_value: Any, existing_item_identifying_value: Any) -> bool:
        if isinstance(item_identifying_value, list):
            item_identifying_value = sorted(item_identifying_value)
        if isinstance(existing_item_identifying_value, list):
            existing_item_identifying_value = sorted(existing_item_identifying_value)
        return item_identifying_value == existing_item_identifying_value

    def reorder_item_properties(item: dict) -> None:
        if isinstance(item, dict):
            item = sort_dictionary(item)
            if (uuid := item.get(_ITEM_UUID_PROPERTY_NAME)) is not None:
                del item[_ITEM_UUID_PROPERTY_NAME]
                item = {_ITEM_UUID_PROPERTY_NAME: uuid, **item}
        return item

    if not isinstance(portal, (Portal, PortalFromUtils)):
        return False if report is True else []

    if not (identifying_properties := portal.get_identifying_property_names(item_type)):
        return False if report is True else []

    if _ITEM_UUID_PROPERTY_NAME in identifying_properties:
        identifying_properties.remove(_ITEM_UUID_PROPERTY_NAME)
        if not identifying_properties:
            return False if report is True else []

    if not callable(printf):
        printf = print

    conflicts = []

    item_uuid = item.get(_ITEM_UUID_PROPERTY_NAME)
    if item_uuid == "11f94a17-51ed-4a0f-93b1-1cac2fd2844f":
        pass

    existing_items_found = 0

    item_conflicts = []
    for identifying_property in identifying_properties:
        if (identifying_values := item.get(identifying_property)) is not None:
            if not isinstance(identifying_values, list):
                identifying_values = [identifying_values]
            for identifying_value in identifying_values:
                if (existing_item := get_portal_item_metadata(portal, item_type,
                                                              identifying_property, identifying_value)) is not None:
                    existing_items_found += 1
                    if (existing_item_uuid := existing_item.get(_ITEM_UUID_PROPERTY_NAME)) != item_uuid:
                        item_conflicts.append({
                            "identifying_property": identifying_property,
                            "identifying_value": identifying_value,
                            "item_uuid": item_uuid,
                            "existing_item_uuid": existing_item_uuid
                        })
    if item_conflicts:
        conflicts.append({
            "conflict": {
                "type": item_type,
                "identifying_properties": identifying_properties,
                "conflicts": item_conflicts,
                "item_source": item_source,
                "item": reorder_item_properties(item),
                "existing_source": portal.env,
                "existing_item": reorder_item_properties(existing_item)
            }
        })

    if (existing_item := get_portal_item_metadata(portal, item_type, _ITEM_UUID_PROPERTY_NAME, item_uuid)) is not None:
        item_conflicts = []
        existing_items_found += 1
        for identifying_property in identifying_properties:
            if (item_identifying_value := item.get(identifying_property)) is None:
                continue
            if (existing_item_identifying_value := existing_item.get(identifying_property)) is None:
                continue
            if not identifying_values_are_equal(item_identifying_value, existing_item_identifying_value):
                item_conflicts.append({
                    "identifying_property": identifying_property,
                    "identifying_value": item_identifying_value,
                    "existing_identifying_value": existing_item_identifying_value
                })
        if item_conflicts:
            conflicts.append({
                "conflict": {
                    "type": item_type,
                    "uuid": item_uuid,
                    "identifying_properties": identifying_properties,
                    "conflicts": item_conflicts,
                    "item_source": item_source,
                    "item": reorder_item_properties(item),
                    "existing_source": portal.env,
                    "existing_item": reorder_item_properties(existing_item)
                }
            })

    if debug is True:
        message = f"Checking item for conflicts: /{item_type}/{item_uuid} ... "
        if conflicts:
            message += "conflicts found:"
            message += "\n" + json.dumps(conflicts, indent=4)
        else:
            message += f"OK {chars.dot} found: {existing_items_found}"
        printf(message)
    elif (report is True) and conflicts:
        message = f"Conflicts found in item: /{item_type}/{item_uuid}"
        message += "\n" + json.dumps(conflicts, indent=4)
        printf(message)

    return conflicts if (report is not True) else (len(conflicts) > 0)


@lru_cache(maxsize=1024)
def get_portal_item_metadata(portal: Portal, item_type: str,
                             identifying_property: str, identifying_value: Any) -> Optional[dict]:
    return portal.get_metadata(f"/{item_type}/{identifying_value}", raw=True, raise_exception=False)


if __name__ == "__main__":
    status = main()
    sys.exit(status if isinstance(status, int) else 0)
