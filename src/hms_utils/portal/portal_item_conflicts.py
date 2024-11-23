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
from hms_utils.version_utils import get_version

_ITEM_SID_PROPERTY_NAME = "sid"
_ITEM_UUID_PROPERTY_NAME = "uuid"
_ITEM_TYPE_PSEUDO_PROPERTY_NAME = "@@@__TYPE__@@@"
_ITEM_IGNORE_REF_PROPERTIES = ["viewconfig", "higlass_uid", "blob_id"]


def main():

    argv = ARGV({
        ARGV.REQUIRED(str): ["--retrieved"],  # noqa
        ARGV.REQUIRED(str): ["--existing"],
        ARGV.OPTIONAL(bool): ["--ping"],
        ARGV.OPTIONAL(bool): ["--version"],
        ARGV.OPTIONAL(bool): ["--verbose"],
        ARGV.OPTIONAL(bool): ["--debug"],
        ARGV.OPTIONAL(str): ["--app"],
        ARGV.OPTIONAL(str): ["--env", "--e"],
        ARGV.OPTIONAL(str): ["--ini", "--ini-file"],
        ARGV.OPTIONAL(int, 0): ["--threads"]
    })

    if argv.version:
        print(f"hms-portal-read: {get_version()}")

    if not (portal := Portal.create(argv.env or argv.ini, app=argv.app,
                                    verbose=argv.verbose, debug=argv.debug, ping=argv.ping)):
        return 1

    if not os.path.isdir(existing_items_source := os.path.expanduser(argv.existing)):
        if not (existing_items_source := Portal.create(argv.existing)):
            print(f"Cannot access existing portal specified by given environment: {argv.existing}")
            sys.exit(1)

    if os.path.isdir(retrieved_items_directory := os.path.expanduser(argv.retrieved)):
        if retrieved_items_files := glob.glob(os.path.join(retrieved_items_directory, "*.json")):
            for retrieved_items_file in retrieved_items_files:
                if not retrieved_items_file.endswith(".json"):
                    print(f"WARNING: File name for retrieved items does not end with .json: {retrieved_items_file}")
                    continue
                if not (retrieved_item_type := Portal.schema_name(retrieved_items_file)):
                    print(f"WARNING: File name for retrieved items does not corresond to known item type name:"
                          f" {retrieved_items_file}")
                    continue
                try:
                    with io.open(retrieved_items_file) as f:
                        if not isinstance(retrieved_items_for_type := json.load(f), list):
                            print(f"WARNING: File for retrieved items deos not contain a JSON list:"
                                  f" {retrieved_items_file}")
                            continue
                except Exception:
                    print(f"WARNING: File for retrieved items does not contain valid JSON:"
                          f" {retrieved_items_file}")
                    continue
                if argv.threads >= 0:
                    def report_conflict_exists_function(retrieved_item: dict) -> None:
                        nonlocal argv, portal, retrieved_item_type, retrieved_items_file, existing_items_source
                        conflict_exists(portal,
                                        item=retrieved_item,
                                        item_type=retrieved_item_type,
                                        item_source=retrieved_items_file,
                                        existing_source=existing_items_source,
                                        report=True, debug=argv.debug)
                    conflict_exists_functions = []
                    for retrieved_item in retrieved_items_for_type:
                        conflict_exists_functions.append(
                            lambda retrieved_item=retrieved_item: report_conflict_exists_function(retrieved_item))
                    run_concurrently(conflict_exists_functions, nthreads=argv.threads)
                else:
                    for retrieved_item in retrieved_items_for_type:
                        if retrieved_items_conflicts := conflict_exists(portal,
                                                                        item=retrieved_item,
                                                                        item_type=retrieved_item_type,
                                                                        item_source=retrieved_items_file,
                                                                        existing_source=existing_items_source,
                                                                        debug=argv.debug):
                            print("CONFLICT:")
                            print(json.dumps(retrieved_items_conflicts, indent=4))
    elif os.path.isfile(retrieved_items_file := os.path.expanduser(argv.retrieved)):
        print("TODO")
        sys.exit(1)


def conflicts_exist(portal: Portal, items: dict,
                    items_source: Optional[Union[Portal, str]] = None,
                    existing_source: Optional[Portal, str] = None, debug: bool = False) -> List[dict]:
    conflicts = []
    for item_type in items:
        for item in items[item_type]:
            if item_conflicts := conflict_exists(portal, item, item_type,
                                                 item_source=items_source,
                                                 existing_source=existing_source, debug=debug):
                conflicts.extend(item_conflicts)
    return conflicts


def conflict_exists(portal: Portal, item: dict, item_type: Optional[str] = None,
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
                if debug:
                    printf(f"Checking retrieved item for conflicts: /{item_type}/{identifying_value}")
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
                        if report is True:
                            printf("CONFLICT FOUND:")
                            printf(json.dumps(conflict, indent=4))
                        else:
                            conflicts.append(conflict)

    if debug:
        printf(f"Checking retrieved item for conflicts: /{item_type}/{item_uuid}")
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
            if report is True:
                printf("CONFLICT FOUND:")
                printf(json.dumps(conflict, indent=4))
            else:
                conflicts.append(conflict)
    return conflicts if (report is not True) else (len(conflicts) > 0)


if __name__ == "__main__":
    status = main()
    sys.exit(status if isinstance(status, int) else 0)
