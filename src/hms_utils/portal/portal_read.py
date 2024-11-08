# TODO: Rewrite/refactor view_portal_object.py

from functools import lru_cache
import io
import json
import os
import requests
import sys
from typing import List, Optional, Union
from dcicutils.captured_output import captured_output
from dcicutils.command_utils import yes_or_no
from dcicutils.misc_utils import to_snake_case
from hms_utils.argv import ARGV
from hms_utils.chars import chars
from hms_utils.dictionary_utils import sort_dictionary
from hms_utils.portal.portal_utils import Portal
from hms_utils.threading_utils import run_concurrently
from hms_utils.type_utils import get_referenced_uuids, is_uuid, to_non_empty_string_list


_ITEM_IGNORE_PROPERTIES_INSERTS = [
    # "date_created",
    # "last_modified",
    # "principals_allowed",
    # "submitted_by",
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
        ARGV.OPTIONAL(bool): ["--inserts", "--insert"],
        ARGV.OPTIONAL(str): ["--output", "--out", "--o"],
        ARGV.OPTIONAL(bool): ["--raw"],
        ARGV.OPTIONAL(bool): ["--database"],
        ARGV.OPTIONAL(bool): ["--metadata"],
        ARGV.OPTIONAL(bool): ["--nometadata"],
        ARGV.OPTIONAL(bool): ["--noformat"],
        ARGV.OPTIONAL(bool): ["--deleted"],
        ARGV.OPTIONAL(bool): ["--json"],
        ARGV.OPTIONAL(bool): ["--yaml", "--yml"],
        ARGV.OPTIONAL(bool): ["--refs", "--ref"],
        ARGV.OPTIONAL(bool): ["--noignore-properties", "--noignore", "--no-ignore-properties", "--all"],
        ARGV.OPTIONAL(str): ["--ignore-properties", "--ignore"],
        ARGV.OPTIONAL(bool): ["--sort"],
        ARGV.OPTIONAL(int): ["--limit", "--count"],
        ARGV.OPTIONAL(int): ["--offset", "--skip", "--from"],
        ARGV.OPTIONAL(bool): ["--merge"],
        ARGV.OPTIONAL(bool): ["--overwrite"],
        ARGV.OPTIONAL(bool): ["--show"],
        ARGV.OPTIONAL(bool): ["--verbose"],
        ARGV.OPTIONAL(bool): ["--debug"],
        ARGV.OPTIONAL(bool): ["--version"],
        ARGV.OPTIONAL(bool): ["--exceptions", "--exception", "--except"],
        ARGV.OPTIONAL(int, 32): ["--nthreads", "--threads"],
        ARGV.OPTIONAL(bool): ["--argv"],
        ARGV.AT_MOST_ONE_OF: ["--inserts", "--raw"],
        ARGV.AT_MOST_ONE_OF: ["--inserts-files", "--raw"],
        ARGV.AT_MOST_ONE_OF: ["--metadata", "--nometadata"],
        ARGV.AT_LEAST_ONE_OF: ["--env", "--ini"],
        ARGV.DEPENDENCY: ["--no-ignore-properties", ARGV.DEPENDS_ON, ["--raw", "--inserts"]]
    })

    _setup_debugging(argv)

    portal = _create_portal(env=argv.env, ini=argv.ini, app=argv.app,
                            show=argv.show, verbose=argv.verbose, debug=argv.debug)

    # By default use Portal.get_metadata, iff the given query argument does not start with a slash,
    # otherwise use Portal.get; override to use portal.get_metadata with the --metadata
    # option or override to use portal.get with the --nometadata option.
    metadata = (argv.metadata or (not argv.arg.startswith("/"))) and (not argv.nometadata)

    if (not metadata) and (not argv.arg.startswith("/")):
        argv.arg = f"/{argv.arg}"

    if items := _portal_get(portal, argv.arg, metadata=metadata, raw=argv.raw, inserts=argv.inserts,
                            limit=argv.limit, offset=argv.offset, deleted=argv.deleted, nthreads=argv.nthreads):
        if graph := items.get("@graph"):
            items = graph
    if isinstance(items, dict):
        items = [items]

    if argv.refs:
        items.extend(_get_portal_referenced_items(
            portal, items, raw=argv.raw, metadata=argv.metadata,
            inserts=argv.inserts, database=argv.database, nthreads=argv.nthreads))

    if not argv.noignore_properties:
        if not (argv.ignore_properties and
                (ignore_properties := to_non_empty_string_list(argv.ignore_properties.split(",")))):
            ignore_properties = _ITEM_IGNORE_PROPERTIES_INSERTS
        _remove_ignored_properties(items, ignore_properties)

    if argv.inserts:
        items_by_type = {}
        for item in items:
            item_type = item.get(_ITEM_TYPE_PSEUDO_PROPERTY_NAME)
            if not (item_list := items_by_type.get(item_type)):
                items_by_type[item_type] = (item_list := [])
            item_list.append(item)
            del item[_ITEM_TYPE_PSEUDO_PROPERTY_NAME]
        items = items_by_type

    if argv.sort:
        items = sort_dictionary(items)

    # TODO: Organize by type at least for --inserts ...
    # object_type = portal.get_schema_type(items)
    # if argv.debug:
    #     _print(f"OBJECT TYPE: {object_type}")

    if argv.output:
        if argv.inserts and (os.path.isdir(argv.output) or argv.output.endswith(os.sep)):
            _print_items_inserts(items, argv.output, overwrite=argv.overwrite, merge=argv.merge, noformat=argv.noformat)
        else:
            overwriting_output_file = False
            if os.path.isdir(argv.output):
                _error(f"Specified output file already exists as a directory: {argv.output}")
            elif os.path.exists(argv.output):
                if not argv.overwrite:
                    _print(f"Specified output file already exists: {argv.output}")
                    if not yes_or_no("Overwrite this file?"):
                        return
                overwriting_output_file = True
            with io.open(argv.output, "w") as f:
                json.dump(items, f, indent=None if argv.noformat else 4)
            if overwriting_output_file:
                _verbose(f"Output file overwritten: {argv.output}")
            else:
                _verbose(f"Output file written: {argv.output}")
    elif argv.noformat:
        _print(items)
    else:
        _print(json.dumps(items, indent=4))


def _print_items_inserts(items: dict, output_directory: str,
                         overwrite: bool = False, merge: bool = False, noformat: bool = False) -> None:
    os.makedirs(output_directory, exist_ok=True)
    for item_type in items:
        item_type_items = items[item_type]
        output_file = os.path.join(output_directory, f"{to_snake_case(item_type)}.json")
        merge_into_output_file = False
        overwriting_output_file = False
        if os.path.exists(output_file):
            if merge:
                merge_into_output_file = True
            elif overwrite:
                overwriting_output_file = True
            else:
                _print(f"Specified output file already exists: {output_file} {chars.dot}")
                if not yes_or_no("Overwrite this file?"):
                    if not yes_or_no("Merge into this file?"):
                        continue
                    merge_into_output_file = True
                else:
                    overwriting_output_file = True
        if merge_into_output_file:
            try:
                with io.open(output_file, "r") as f:
                    if not isinstance(existing_items := json.load(f), list):
                        _print(f"JSON file does not contain a list: {output_file}")
                        continue
                    existing_items.append(item_type_items)
                    item_type_items = existing_items
            except Exception:
                _print(f"Cannot load file as JSON: {output_file}")
                continue
        with io.open(output_file, "w") as f:
            if overwriting_output_file:
                _debug(f"Overwriting output file: {output_file}")
            elif merge_into_output_file:
                _debug(f"Merging into output file: {output_file}")
            else:
                _debug(f"Writing into output file: {output_file}")
            json.dump(item_type_items, f, indent=None if (noformat is True) else 4)
            if overwriting_output_file:
                _verbose(f"Output file overwritten: {output_file}")
            elif merge_into_output_file:
                _verbose(f"Output file merged: {output_file}")
            else:
                _verbose(f"Output file written: {output_file}")


def _get_portal_referenced_items(portal: Portal, item: dict, metadata: bool = False,
                                 raw: bool = False, inserts: bool = False, database: bool = False,
                                 nthreads: Optional[int] = None) -> List[dict]:
    referenced_items = [] ; ignore_uuids = []  # noqa
    while referenced_uuids := get_referenced_uuids(item, ignore_uuids=ignore_uuids,
                                                   exclude_uuid=True, include_paths=True):
        items = _get_portal_items_for_uuids(
            portal, referenced_uuids, metadata=metadata, raw=raw, inserts=inserts, database=database, nthreads=nthreads)
        referenced_items.extend(items)
        for item in items:
            if item_uuid := item.get(_ITEM_UUID_PROPERTY_NAME):
                if item_uuid not in ignore_uuids:
                    ignore_uuids.append(item_uuid)
    return referenced_items


def _get_portal_items_for_uuids(portal: Portal, uuids: Union[List[str], str], metadata: bool = False,
                                raw: bool = False, inserts: bool = False, database: bool = False,
                                nthreads: Optional[int] = None) -> List[dict]:
    items = []
    if not isinstance(uuids, list):
        if not is_uuid(uuids):
            return []
        uuids = [uuids]
    fetch_portal_item_functions = []
    def fetch_portal_item(uuid: str) -> Optional[dict]:  # noqa
        nonlocal portal, metadata, raw, database, items
        if item := _portal_get(portal, uuid, metadata=True,
                               raw=raw, inserts=inserts, database=database, nthreads=nthreads):
            # TODO: make thread-safe.
            items.append(item)
    if fetch_portal_item_functions := [lambda uuid=uuid: fetch_portal_item(uuid) for uuid in uuids if is_uuid(uuid)]:
        run_concurrently(fetch_portal_item_functions, nthreads=nthreads)
    return items


@lru_cache(maxsize=1024)
def _portal_get(portal: Portal, query: str, metadata: bool = False, raw: bool = False,
                inserts: bool = False, database: bool = False,
                limit: Optional[int] = None, offset: Optional[int] = None, deleted: bool = False,
                nthreads: Optional[int] = None) -> dict:
    try:
        if inserts is True:
            return _portal_get_inserts(portal, query, metadata=metadata, database=database,
                                       limit=limit, offset=offset, deleted=deleted, nthreads=nthreads)
        elif metadata is True:
            _debug(f"portal.get_metadata {chars.dot} raw: {raw} {chars.dot} database: {database}")
            return portal.get_metadata(query, raw=raw, database=database, limit=limit, offset=offset, deleted=deleted)
        else:
            _debug(f"portal.get {chars.dot} raw: {raw} {chars.dot} database: {database}")
            return portal.get(query, raw=raw, database=database, limit=limit, offset=offset, deleted=deleted).json()
    except Exception:
        global _exceptions
        if _exceptions: raise  # noqa
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
def _portal_get_inserts(portal: Portal, query: str, metadata: bool = False, database: bool = False,
                        limit: Optional[int] = None, offset: Optional[int] = None,
                        deleted: bool = False,
                        nthreads: Optional[int] = None) -> dict:
    global _exceptions
    try:
        item = None ; item_noraw = None  # noqa
        def fetch_portal_item() -> None:  # noqa
            nonlocal portal, query, database, item
            try:
                if metadata is True:
                    _debug(f"portal.get_metadata: {query} {chars.dot} inserts: True {chars.dot}"
                           f" raw: True {chars.dot} database: {database}")
                    item = portal.get_metadata(query, raw=True, database=database,
                                               limit=limit, offset=offset, deleted=deleted)
                else:
                    _debug(f"portal.get: {query} {chars.dot} inserts: True {chars.dot}"
                           f" raw: True {chars.dot} database: {database}")
                    item = portal.get(query, raw=True, database=database,
                                      limit=limit, offset=offset, deleted=deleted).json()
            except Exception:
                if _exceptions: raise  # noqa
        def fetch_portal_item_noraw() -> None:  # noqa
            # This is to get the non-raw frame item format which has the type information (the raw frame does not).
            nonlocal portal, query, metadata, database, item_noraw
            try:
                if metadata is True:
                    _debug(f"portal.get_metadata: {query} {chars.dot} inserts: True {chars.dot}"
                           f" raw: False {chars.dot} database: {database}")
                    item_noraw = portal.get_metadata(query, raw=False, database=database,
                                                     limit=limit, offset=offset, deleted=deleted,
                                                     field=_ITEM_UUID_PROPERTY_NAME)
                else:
                    _debug(f"portal.get: {query} {chars.dot} inserts: True {chars.dot}"
                           f" raw: False {chars.dot} database: {database}")
                    item_noraw = portal.get(query, raw=False, database=database,
                                            limit=limit, offset=offset, deleted=deleted,
                                            field=_ITEM_UUID_PROPERTY_NAME).json()
            except Exception:
                if _exceptions: raise  # noqa
        run_concurrently([fetch_portal_item, fetch_portal_item_noraw], nthreads=min(2, nthreads))
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
        if _exceptions: raise  # noqa
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
        if portal.env:
            _verbose(f"Portal environment: {portal.env}")
        if portal.keys_file:
            _verbose(f"Portal keys file: {portal.keys_file}")
        if portal.key_id:
            if show:
                _verbose(f"Portal key: {portal.key_id} {chars.dot} {portal.secret}")
            else:
                _verbose(f"Portal key prefix: {portal.key_id[0:2]}******")
        if portal.ini_file:
            _verbose(f"Portal ini file: {portal.ini_file}")
        if portal.server:
            _verbose(f"Portal server: {portal.server}")
    if ping:
        if portal.ping():
            _verbose(f"Portal connectivity: OK {chars.check}")
        else:
            _error(f"Portal connectivity: ERROR {chars.xmark}")
    return portal


def _print(*args, **kwargs) -> None:
    print(*args, **kwargs)


def _verbose(*args, **kwargs) -> None:
    _print(*args, **kwargs, file=sys.stderr, flush=True)


def _debug(message: str) -> None:
    _print(f"DEBUG: {message}", file=sys.stderr, flush=True)


def _error(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr, flush=True)
    sys.exit(1)


def _nofunction(*args, **kwargs) -> None:
    pass


def _setup_debugging(argv: ARGV) -> None:

    global _verbose, _debug, _nofunction, _exceptions
    if not argv.verbose: _verbose = _nofunction  # noqa
    if not argv.debug: _debug = _nofunction  # noqa
    if argv.exceptions: _exceptions = True  # noqa

    original_requests_get = requests.get
    def requests_get(*args, **kwargs):  # noqa
        _debug(f"requests.get {chars.dot} args: {args} {chars.dot} {kwargs}")
        return original_requests_get(*args, **kwargs)
    requests.get = requests_get

    if argv.argv:
        _print(json.dumps(argv._dict, indent=4))


_exceptions = False


if __name__ == "__main__":
    main()
