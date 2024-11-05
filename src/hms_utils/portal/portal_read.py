# TODO: Rewrite/refactor view_portal_object.py

from functools import lru_cache
import io
import json
import os
import sys
from typing import Any, List, Optional, Union
from dcicutils.captured_output import captured_output
from hms_utils.argv import ARGV
from hms_utils.chars import chars
from hms_utils.portal.portal_utils import Portal
from hms_utils.threading_utils import run_concurrently
from hms_utils.type_utils import is_uuid

_DEFAULT_IGNORE_PROPERTIES = [
    "date_created",
    "last_modified",
    "principals_allowed",
    "submitted_by",
    "schema_version"
]
_UUID_PROPERTY_NAME = "uuid"


def main():

    argv = ARGV({
        ARGV.REQUIRED(str, "/users"): ["arg"],
        ARGV.OPTIONAL(str): ["--app"],
        ARGV.OPTIONAL(str, "smaht-local"): ["--env", "--e"],
        ARGV.OPTIONAL(str): ["--ini", "--ini-file"],
        ARGV.OPTIONAL(bool): ["--inserts"],
        ARGV.OPTIONAL(bool): ["--insert-files"],
        ARGV.OPTIONAL(str): ["--output", "--out"],
        ARGV.OPTIONAL(bool): ["--raw"],
        ARGV.OPTIONAL(bool): ["--database"],
        ARGV.OPTIONAL(bool): ["--noformat"],
        ARGV.OPTIONAL(bool): ["--json"],
        ARGV.OPTIONAL(bool): ["--yaml", "--yml"],
        ARGV.OPTIONAL(bool): ["--refs", "--ref"],
        ARGV.OPTIONAL(bool): ["--all-properties", "--all"],
        ARGV.OPTIONAL(int): ["--limit", "--count"],
        ARGV.OPTIONAL(int): ["--offset", "--skip", "--from"],
        ARGV.OPTIONAL(int, 32): ["--nthreads", "--threads"],
        ARGV.OPTIONAL([str]): ["--ignore-properties", "--ignore"],
        ARGV.OPTIONAL(bool): ["--show"],
        ARGV.OPTIONAL(bool): ["--verbose"],
        ARGV.OPTIONAL(bool): ["--debug"],
        ARGV.OPTIONAL(bool): ["--version"],
        ARGV.OPTIONAL(bool): ["--argv"],
        ARGV.AT_MOST_ONE_OF: ["--inserts", "--raw"],
        # ARGV.AT_LEAST_ONE_OF: ["--env", "--ini"],
        ARGV.DEPENDENCY: ["--all-properties", ARGV.DEPENDS_ON, ["--raw", "--inserts"]]
    })

    if argv.argv:
        print(json.dumps(argv._dict, indent=4))

    portal = _create_portal(env=argv.env, ini=argv.ini, app=argv.app,
                            show=argv.show, verbose=argv.verbose, debug=argv.debug)

    if argv.output and os.path.exists(argv.output):
        _error(f"Specified output file already exists: {argv.output}")

    if argv.arg.startswith("/"):
        if isinstance(argv.limit, int):
            if ("?limit=" not in argv.arg) and ("&limit=" not in argv.arg):
                argv.arg += f"&limit={argv.limit}" if "?" in argv.arg else f"?limit={argv.limit}"
        if isinstance(argv.offset, int):
            if ("?from=" not in argv.arg) and ("&from=" not in argv.arg):
                argv.arg += f"&from={argv.offset}" if "?" in argv.arg else f"?from={argv.offset}"
        portal_get = _portal_get
    else:
        portal_get = _portal_get_metadata

    if items := portal_get(portal, argv.arg, raw=argv.raw or argv.inserts):
        if graph := items.get("@graph"):
            items = graph
    if isinstance(items, dict):
        items = [items]

    referenced_items = _get_portal_referenced_items(
        portal, items, raw=argv.raw, database=argv.database, nthreads=argv.nthreads) if argv.refs else []

    if not argv.all_properties:
        _remove_ignored_properties(items, _DEFAULT_IGNORE_PROPERTIES)
        _remove_ignored_properties(referenced_items, _DEFAULT_IGNORE_PROPERTIES)

    items.extend(referenced_items)

    # TODO: Organize by type at least for --inserts ...
    # object_type = portal.get_schema_type(items)
    # if argv.debug:
    #     _print(f"OBJECT TYPE: {object_type}")

    if argv.output:
        with io.open(argv.output, "w") as f:
            json.dump(items, f, indent=None if argv.noformat else 4)
        if argv.verbose:
            _print(f"Output file written: {argv.output}")
    elif argv.noformat:
        _print(items)
    else:
        _print(json.dumps(items, indent=4))


def _get_portal_referenced_items(portal: Portal, item: dict, raw: bool = False,
                                 database: bool = False, nthreads: Optional[int] = None) -> List[dict]:
    referenced_items = [] ; ignore_uuids = []  # noqa
    while referenced_uuids := _get_referenced_uuids(item, ignore_uuids=ignore_uuids):
        referenced_items = _get_portal_items_for_uuids(
            portal, referenced_uuids, raw=raw, database=database, nthreads=nthreads)
        ignore_uuids.extend([item.get(_UUID_PROPERTY_NAME) for item in referenced_items])
    return referenced_items


def _get_referenced_uuids(item: Union[dict, List[dict]], ignore_uuids: Optional[List[str]] = None) -> List[str]:
    referenced_uuids = []
    def find_referenced_uuids(item: Any) -> None:  # noqa
        nonlocal referenced_uuids, ignore_uuids
        if isinstance(item, dict):
            for value in item.values():
                find_referenced_uuids(value)
        elif isinstance(item, (list, tuple)):
            for element in item:
                find_referenced_uuids(element)
        elif uuids := _get_uuids_from_value(item):
            for uuid in uuids:
                if (uuid not in ignore_uuids) and (uuid not in referenced_uuids):
                    referenced_uuids.append(uuid)
    if not isinstance(ignore_uuids, list):
        ignore_uuids = []
    if isinstance(item, dict):
        if (uuid := item.get(_UUID_PROPERTY_NAME)) and (uuid not in ignore_uuids):
            ignore_uuids.append(uuid)
    elif isinstance(item, list):
        for item in item:
            if (uuid := item.get(_UUID_PROPERTY_NAME)) and (uuid not in ignore_uuids):
                ignore_uuids.append(uuid)
    find_referenced_uuids(item)
    return referenced_uuids


def _get_portal_items_for_uuids(portal: Portal, uuids: Union[List[str], str],
                                raw: bool = False, database: bool = False,
                                nthreads: Optional[int] = None) -> List[str]:
    items = []
    if not isinstance(uuids, list):
        if not (isinstance(uuids, str) and is_uuid(uuids)):
            return []
        uuids = [uuids]
    fetch_item_functions = []
    def fetch_portal_item(uuid: str) -> Optional[dict]:  # noqa
        nonlocal portal, raw, database, items
        if item := _portal_get_metadata(portal, uuid, raw=raw, database=database):
            items.append(item)
    if fetch_item_functions := [lambda uuid=uuid: fetch_portal_item(uuid) for uuid in uuids if is_uuid(uuid)]:
        run_concurrently(fetch_item_functions, nthreads=nthreads)
    return items


@lru_cache(maxsize=1024)
def _portal_get_metadata(portal: Portal, uuid: str, raw: bool = False, database: bool = False) -> dict:
    try:
        return portal.get_metadata(uuid, raw=raw, database=database, raise_exception=False)
    except Exception:
        pass
    return {}


@lru_cache(maxsize=64)
def _portal_get(portal: Portal, path: str, raw: bool = False, database: bool = False) -> dict:
    try:
        return portal.get(path, raw=raw, database=database, raise_exception=False).json()
    except Exception:
        pass
    return {}


def _get_uuids_from_value(value: str) -> List[str]:
    uuids = []
    if isinstance(value, str):
        if is_uuid(value):
            uuids.append(value)
        else:
            for component in value.split("/"):
                if is_uuid(component := component.strip()):
                    uuids.append(component)
    return uuids


def _remove_ignored_properties(items: Union[List[dict], dict], ignored_properties: List[str]) -> None:
    if isinstance(items, dict):
        items = [items]
    elif not isinstance(items, list):
        return
    for item in items:
        for key in list(item.keys()):
            if key in ignored_properties:
                del item[key]


def _create_portal(env: Optional[str] = None, ini: Optional[str] = None, app: Optional[str] = None,
                   ping: bool = True, show: bool = False, verbose: bool = False, debug: bool = False) -> Portal:
    portal = None ; error = None  # noqa
    with captured_output(not debug):
        try:
            portal = Portal(env, app=app) if env or app else Portal(ini)
        except Exception as e:
            error = e
    if error:
        _error(str(error))
    if portal:
        if verbose:
            if portal.env:
                _print(f"Portal environment: {portal.env}")
            if portal.keys_file:
                _print(f"Portal keys file: {portal.keys_file}")
            if portal.key_id:
                if show:
                    _print(f"Portal key: {portal.key_id} {chars.dot} {portal.secret}")
                else:
                    _print(f"Portal key prefix: {portal.key_id[0:2]}******")
            if portal.ini_file:
                _print(f"Portal ini file: {portal.ini_file}")
            if portal.server:
                _print(f"Portal server: {portal.server}")
    if ping:
        if portal.ping():
            if verbose:
                _print(f"Portal connectivity: OK {chars.check}")
        else:
            _print(f"Portal connectivity: ERROR {chars.xmark}")
    return portal


def _print(*args, **kwargs) -> None:
    print(*args, **kwargs)


def _verbose(*args, **kwargs) -> None:
    _print(*args, **kwargs, file=sys.stderr, flush=True)


def _error(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr, flush=True)
    sys.exit(1)


if __name__ == "__main__":
    main()
