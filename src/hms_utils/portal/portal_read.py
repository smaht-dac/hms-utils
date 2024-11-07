# TODO: Rewrite/refactor view_portal_object.py

from functools import lru_cache
import io
import json
import os
import sys
from typing import List, Optional, Union
from dcicutils.captured_output import captured_output
from hms_utils.argv import ARGV
from hms_utils.chars import chars
from hms_utils.portal.portal_utils import Portal
from hms_utils.threading_utils import run_concurrently
from hms_utils.type_utils import get_referenced_uuids, is_uuid, to_non_empty_string_list


_ITEM_IGNORE_PROPERTIES_DEFAULT = [
    "date_created",
    "last_modified",
    "principals_allowed",
    "submitted_by",
    "schema_version"
]
_ITEM_UUID_PROPERTY_NAME = "uuid"
_ITEM_TYPE_PSEUDO_PROPERTY_NAME = "@@@__TYPE__@@@"


def main():

    argv = ARGV({
        ARGV.REQUIRED(str): ["arg"],
        ARGV.OPTIONAL(str): ["--app"],
        ARGV.OPTIONAL(str): ["--env", "--e"],
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
        ARGV.OPTIONAL(int, 1): ["--nthreads", "--threads"],
        ARGV.OPTIONAL([str]): ["--ignore-properties", "--ignore"],
        ARGV.OPTIONAL(bool): ["--show"],
        ARGV.OPTIONAL(bool): ["--verbose"],
        ARGV.OPTIONAL(bool): ["--debug"],
        ARGV.OPTIONAL(bool): ["--version"],
        ARGV.OPTIONAL(bool): ["--argv"],
        ARGV.AT_MOST_ONE_OF: ["--inserts", "--raw"],
        ARGV.AT_LEAST_ONE_OF: ["--env", "--ini"],
        ARGV.DEPENDENCY: ["--all-properties", ARGV.DEPENDS_ON, ["--raw", "--inserts"]]
    })

    global _debug, _verbose, _nofunction
    if not argv.debug: _debug = _nofunction  # noqa
    if not argv.verbose: _verbose = _nofunction  # noqa

    if argv.argv:
        _print(json.dumps(argv._dict, indent=4))

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

    metadata = not argv.arg.startswith("/")

    if items := _portal_get(portal, argv.arg, metadata=metadata, raw=argv.raw, inserts=argv.inserts):
        if graph := items.get("@graph"):
            items = graph
    if isinstance(items, dict):
        items = [items]

    if argv.refs:
        items.extend(_get_portal_referenced_items(
            portal, items, raw=argv.raw, inserts=argv.inserts, database=argv.database, nthreads=argv.nthreads))

    if not argv.all_properties:
        _remove_ignored_properties(items, _ITEM_IGNORE_PROPERTIES_DEFAULT)

    if argv.inserts:
        items_by_type = {}
        for item in items:
            item_type = item.get(_ITEM_TYPE_PSEUDO_PROPERTY_NAME)
            if not (item_list := items_by_type.get(item_type)):
                items_by_type[item_type] = (item_list := [])
            item_list.append(item)
            pass
            del item[_ITEM_TYPE_PSEUDO_PROPERTY_NAME]
        items = items_by_type

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


def _get_portal_referenced_items(portal: Portal, item: dict, raw: bool = False, inserts: bool = False,
                                 database: bool = False, nthreads: Optional[int] = None) -> List[dict]:
    referenced_items = [] ; ignore_uuids = []  # noqa
    while referenced_uuids := get_referenced_uuids(item, ignore_uuids=ignore_uuids,
                                                   exclude_uuid=True, include_paths=True):
        referenced_items = _get_portal_items_for_uuids(
            portal, referenced_uuids, raw=raw, inserts=inserts, database=database, nthreads=nthreads)
        ignore_uuids.extend([item.get(_ITEM_UUID_PROPERTY_NAME) for item in referenced_items])
    return referenced_items


def _get_portal_items_for_uuids(portal: Portal, uuids: Union[List[str], str],
                                raw: bool = False, inserts: bool = False, database: bool = False,
                                nthreads: Optional[int] = None) -> List[dict]:
    items = []
    if not isinstance(uuids, list):
        if not is_uuid(uuids):
            return []
        uuids = [uuids]
    fetch_portal_item_functions = []
    def fetch_portal_item(uuid: str) -> Optional[dict]:  # noqa
        nonlocal portal, raw, database, items
        if item := _portal_get(portal, uuid, raw=raw or inserts, inserts=inserts, database=database):
            items.append(item)
    if fetch_portal_item_functions := [lambda uuid=uuid: fetch_portal_item(uuid) for uuid in uuids if is_uuid(uuid)]:
        run_concurrently(fetch_portal_item_functions, nthreads=nthreads)
    return items


@lru_cache(maxsize=1024)
def _portal_get(portal: Portal, uuid: str, metadata: bool = False,
                raw: bool = False, inserts: bool = False, database: bool = False) -> dict:
    try:
        if inserts is True:
            return _portal_get_inserts(portal, uuid, metadata=metadata, database=database)
        else:
            return _portal_get_plain(portal, uuid, metadata=metadata, raw=raw, database=database)
    except Exception:
        pass
    return {}


# Note that /files?limit=3 with raw=True given non-raw result.
# but that /files with raw=True given raw result.
# and that /files?status=released with raw=True gives error
# Oh actually should use portal.get not portal.get_metadata for search.
# These FYI are the same results:
# portal.get("/f8da20ff-1b39-4a8f-af46-1c82ee601374", raw=False).json()
# portal.get_metadata("f8da20ff-1b39-4a8f-af46-1c82ee601374", raw=False)
# And these FYI are the same results:
# portal.get("/f8da20ff-1b39-4a8f-af46-1c82ee601374", raw=True).json()
# portal.get_metadata("f8da20ff-1b39-4a8f-af46-1c82ee601374", raw=True)

@lru_cache(maxsize=1024)
def _portal_get_inserts(portal: Portal, uuid: str, metadata: bool = False, database: bool = False) -> dict:
    try:
        item = None ; item_noraw = None  # noqa
        def fetch_portal_item() -> None:  # noqa
            nonlocal portal, uuid, database, item
            try:
                if metadata is True:
                    item = portal.get_metadata(uuid, raw=True, database=database)
                else:
                    item = portal.get(uuid, raw=True, database=database).json()
            except Exception:
                pass
        def fetch_portal_item_noraw() -> None:  # noqa
            nonlocal portal, uuid, metadata, database, item_noraw
            try:
                if metadata is True:
                    item_noraw = portal.get_metadata(uuid, raw=False, database=database)
                else:
                    item_noraw = portal.get_metadata(uuid, raw=False, database=database)
            except Exception:
                pass
        run_concurrently([fetch_portal_item, fetch_portal_item_noraw], nthreads=2)
        if isinstance(graph := item.get("@graph"), list):
            if isinstance(item_noraw_graph := item_noraw.get("@graph"), list):
                def find_item_type(uuid: str) -> Optional[str]:
                    nonlocal item_noraw, item_noraw_graph
                    for item_element in item_noraw_graph:
                        if item_element.get(_ITEM_UUID_PROPERTY_NAME) == uuid:
                            return get_item_type(item_element)
                    return None
                for graph_item in graph:
                    if graph_item_type := find_item_type(graph_item.get(_ITEM_UUID_PROPERTY_NAME)):
                        graph_item[_ITEM_TYPE_PSEUDO_PROPERTY_NAME] = graph_item_type
        else:
            if item_type := get_item_type(item_noraw):
                item[_ITEM_TYPE_PSEUDO_PROPERTY_NAME] = item_type
        return item
    except Exception:
        pass
    return {}


@lru_cache(maxsize=1024)
def _portal_get_plain(portal: Portal, uuid: str, metadata: bool = False,
                      raw: bool = False, database: bool = False, concurrent: bool = True) -> dict:
    try:
        if metadata is True:
            item = portal.get_metadata(uuid, raw=raw, database=database)
        else:
            item = portal.get(uuid, raw=raw, database=database).json()
        if isinstance(graph := item.get("@graph"), list):
            for graph_item in graph:
                if graph_item_type := get_item_type(graph_item):
                    graph_item[_ITEM_TYPE_PSEUDO_PROPERTY_NAME] = graph_item_type
        else:
            if item_type := get_item_type(item):
                item[_ITEM_TYPE_PSEUDO_PROPERTY_NAME] = item_type
        return item
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


def get_item_type(item: dict) -> Optional[str]:
    if isinstance(item, dict):
        if isinstance(item_types := item.get("@type"), list):
            return item_types[0] if (item_types := to_non_empty_string_list(item_types)) else None
        return item_types if isinstance(item_types, str) and item_types else None
    return None


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


def _debug(*args, **kwargs) -> None:
    _print(*args, **kwargs, file=sys.stderr, flush=True)


def _nofunction(*args, **kwargs) -> None:
    pass


def _error(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr, flush=True)
    sys.exit(1)


if __name__ == "__main__":
    main()
