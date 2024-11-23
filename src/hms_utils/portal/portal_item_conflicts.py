from __future__ import annotations
from functools import lru_cache
import glob
import io
import json
import os
import sys
from typing import Any, Callable, List, Optional, Union
from dcicutils.misc_utils import to_snake_case
from dcicutils.portal_utils import Portal as PortalFromUtils
from hms_utils.argv import ARGV
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
        if not (item_type := Portal.schema_name(file)):
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
        if not (item_type := Portal.schema_name(file)):
            print(f"WARNING: File name does not corresond to known item type name: {file}")
            continue
        try:
            with io.open(file, "r") as f:
                if not isinstance(items := json.load(f), list):
                    print(f"WARNING: File does not contain JSON list: {file}")
                    continue
        except Exception:
            print(f"WARNING: Exception loading JSON from file: {file}")
            continue
        def check_item_for_conflicts_function(item: dict) -> None:  # noqa
            nonlocal argv, portal, file, item_type
            check_item_for_conflicts(portal, item=item, item_type=item_type,
                                     item_source=file, existing_source=portal, report=True, debug=argv.debug)
        if argv.verbose or argv.debug:
            print(f"Checking file for conflicts: {file}")
        if argv.threads > 0:
            check_item_for_conflicts_functions = []
            for item in items:
                check_item_for_conflicts_functions.append(lambda item=item: check_item_for_conflicts_function(item))
            run_concurrently(check_item_for_conflicts_functions, nthreads=argv.threads)
        else:
            for item in items:
                check_item_for_conflicts(portal, item=item, item_type=item_type,
                                         item_source=file, existing_source=portal, report=True, debug=argv.debug)


def check_item_for_conflicts(portal: Portal, item: dict, item_type: Optional[str] = None,
                             item_source: Optional[Union[Portal, str]] = None,
                             existing_source: Optional[Union[Portal, str]] = None,
                             report: bool = False, printf: Optional[Callable] = None,
                             debug: bool = False) -> Union[List[dict], bool]:
    conflicts = []

    if isinstance(item_source, (Portal, PortalFromUtils)):
        item_source = item_source.env
    elif not isinstance(item_source, str):
        item_source = str(item_source)
    if not callable(printf):
        printf = print

    @lru_cache(maxsize=1024)
    def get_item_from_portal(item_type: str, identifying_property: str, identifying_value: Any) -> Optional[dict]:
        nonlocal existing_source
        return existing_source.get_metadata(f"/{item_type}/{identifying_value}", raw=True, raise_exception=False)

    def get_portal_item_source(item_type: str) -> Optional[str]:
        return existing_source.env

    @lru_cache(maxsize=1024)
    def get_item_from_file_system(item_type: str, identifying_property: str, identifying_value: Any) -> Optional[dict]:
        nonlocal existing_source
        if file := get_file_system_item_source(item_type):
            try:
                with io.open(file) as f:
                    if isinstance(items := json.load(f), list):
                        for item in items:
                            if item.get(identifying_property) == identifying_value:
                                return item
            except Exception:
                pass
        return None  # TODO

    def get_file_system_item_source(item_type: str) -> Optional[str]:
        nonlocal existing_source
        file = os.path.join(existing_source, f"{to_snake_case(item_type)}.json")
        return file if os.path.exists(file) else None

    def reorder_item_properties(item: dict) -> None:
        if isinstance(item, dict):
            item = sort_dictionary(item)
            if (uuid := item.get(_ITEM_UUID_PROPERTY_NAME)) is not None:
                del item[_ITEM_UUID_PROPERTY_NAME]
                item = {_ITEM_UUID_PROPERTY_NAME: uuid, **item}
        return item

    if isinstance(existing_source, (Portal, PortalFromUtils)):
        get_existing_item = get_item_from_portal
        get_existing_source = get_portal_item_source
        existing_source_property_name = "existing_item_portal"
    elif isinstance(existing_source, str) and os.path.isdir(existing_source):
        get_existing_item = get_item_from_file_system
        get_existing_source = get_file_system_item_source
        existing_source_property_name = "existing_item_file"
    else:
        return conflicts if report is not True else (len(conflicts) > 0)

    identifying_properties = portal.get_identifying_property_names(item_type)
    item_uuid = item.get(_ITEM_UUID_PROPERTY_NAME)

    for identifying_property in identifying_properties:
        conflicts_item = []
        if (identifying_values := item.get(identifying_property)) is not None:
            if not isinstance(identifying_values, list):
                identifying_values = [identifying_values]
            for identifying_value in identifying_values:
                if (existing_item := get_existing_item(item_type, identifying_property, identifying_value)) is not None:
                    if (existing_item_uuid := existing_item.get(_ITEM_UUID_PROPERTY_NAME)) != item_uuid:
                        conflicts_item.append({
                            "identifying_property": identifying_property,
                            "identifying_value": identifying_value,
                            "retrieved_item_uuid": item_uuid,
                            "existing_item_uuid": existing_item_uuid
                        })
                    if conflicts_item:
                        conflict = {
                            "conflict": {
                                "type": item_type,
                                "identifying_properties": identifying_properties,
                                "conflicts": conflicts_item,
                                "retrieved_item_portal": item_source,
                                "retrieved_item": reorder_item_properties(item),
                                existing_source_property_name: get_existing_source(item_type),
                                "existing_item": reorder_item_properties(existing_item)
                            }
                        }
                        conflicts.append(conflict)

    if (existing_item := get_existing_item(item_type, _ITEM_UUID_PROPERTY_NAME, item_uuid)) is not None:
        conflicts_item = []
        for identifying_property in identifying_properties:
            if (((existing_item_identifying_value := existing_item.get(identifying_property)) is not None) and
                ((item_identifying_value := item.get(identifying_property)) is not None) and
                (existing_item_identifying_value != item_identifying_value)):  # noqa
                conflicts_item.append({
                    "identifying_property": identifying_property,
                    "retrieved_identifying_value": item_identifying_value,
                    "existing_identifying_value": existing_item_identifying_value
                })
        if conflicts_item:
            conflict = {
                "conflict": {
                    "type": item_type,
                    "uuid": item_uuid,
                    "identifying_properties": identifying_properties,
                    "conflicts": conflicts_item,
                    "retrieved_item_portal": item_source,
                    "retrieved_item": reorder_item_properties(item),
                    existing_source_property_name: get_existing_source(item_type),
                    "existing_item": reorder_item_properties(existing_item)
                }
            }
            conflicts.append(conflict)

    if debug is True:
        message = f"Checking item for conflicts: /{item_type}/{item_uuid} ... "
        if conflicts:
            message += "conflicts found:"
            message += "\n" + json.dumps(conflict, indent=4)
        else:
            message += "OK"
        printf(message)
    elif (report is True) and conflicts:
        message = f"Conflicts found in item: /{item_type}/{item_uuid}"
        message += "\n" + json.dumps(conflict, indent=4)
        printf(message)

    return conflicts if (report is not True) else (len(conflicts) > 0)


if __name__ == "__main__":
    status = main()
    sys.exit(status if isinstance(status, int) else 0)
