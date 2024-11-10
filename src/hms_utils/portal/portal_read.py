# TODO: Rewrite/refactor view_portal_object.py

from functools import lru_cache
import io
import json
import os
import requests
import sys
import time
from typing import Any, List, Optional, Set, Tuple, Union
from dcicutils.captured_output import captured_output
from dcicutils.command_utils import yes_or_no
from dcicutils.misc_utils import to_snake_case
from hms_utils.argv import ARGV
from hms_utils.chars import chars
from hms_utils.datetime_utils import format_duration
from hms_utils.dictionary_utils import delete_properties_from_dictionaries, sort_dictionary
from hms_utils.portal.portal_utils import PortalFromUtils
from hms_utils.threading_utils import run_concurrently
from hms_utils.type_utils import contains_uuid, get_referenced_uuids, get_uuids, is_uuid, to_non_empty_string_list
from hms_utils.version_utils import get_version

_ITEM_SID_PROPERTY_NAME = "sid"
_ITEM_UUID_PROPERTY_NAME = "uuid"
_ITEM_TYPE_PSEUDO_PROPERTY_NAME = "@@@__TYPE__@@@"


class Portal(PortalFromUtils):

    _ITEM_IGNORE_PROPERTIES_INSERTS = [
        "date_created",
        "last_modified",
        "schema_version",
        "submitted_by"
    ]

    def __init__(self, *args, exceptions: bool = False, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._get_call_count = 0
        self._get_metadata_call_count = 0
        self._get_call_duration = 0
        self._get_metadata_call_duration = 0
        self._exceptions = exceptions is True
        self._ignore_properties = Portal._ITEM_IGNORE_PROPERTIES_INSERTS

    @property
    def get_call_count(self) -> int:
        return self._get_call_count

    @property
    def get_metadata_call_count(self) -> int:
        return self._get_metadata_call_count

    @property
    def get_call_duration(self) -> float:
        return self._get_call_duration

    @property
    def get_metadata_call_duration(self) -> float:
        return self._get_metadata_call_duration

    @property
    def ignore_properties(self) -> List[str]:
        return self._ignore_properties

    @ignore_properties.setter
    def ignore_properties(self, value: List[str]) -> None:
        self._ignore_properties = value if isinstance(value, list) else []

    def GET(self, query: str, metadata: bool = False,
            raw: bool = False, inserts: bool = False, database: bool = False,
            limit: Optional[int] = None, offset: Optional[int] = None,
            field: Optional[str] = None, deleted: bool = False) -> Optional[Union[List[dict], dict]]:
        try:
            _debug(f"portal.get{'_metadata' if metadata else ''}: {query}"
                   f"{f' {chars.dot} raw' if raw else ''}"
                   f"{f' {chars.dot} database' if database else ''}"
                   f"{f' {chars.dot} limit: {limit}' if isinstance(limit, int) else ''}"
                   f"{f' {chars.dot} offset: {offset}' if isinstance(offset, int) else ''}"
                   f"{f' {chars.dot} field: {field}' if field else ''}"
                   f"{f' {chars.dot} deleted' if deleted else ''}")
            if metadata:
                self._get_metadata_call_count += 1
                started = time.time()
                items = self.get_metadata(query, raw=raw, database=database,
                                          limit=limit, offset=offset, deleted=deleted, field=field)
                self._get_metadata_call_duration += time.time() - started
            else:
                self._get_call_count += 1
                started = time.time()
                items = self.get(query, raw=raw, database=database,
                                 limit=limit, offset=offset, deleted=deleted, field=field).json()
                self._get_call_duration += time.time() - started
        except Exception:
            if self._exceptions:
                raise
        if self._ignore_properties:
            delete_properties_from_dictionaries(items, self._ignore_properties)
        return items

    @staticmethod
    def get_item_type(item: dict) -> Optional[str]:
        if isinstance(item, dict):
            if isinstance(item_types := item.get("@type"), list):
                return item_types[0] if (item_types := to_non_empty_string_list(item_types)) else None
            return item_types if isinstance(item_types, str) and item_types else None
        return None


def main():

    argv = ARGV({
        ARGV.REQUIRED(str): ["query"],
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
        ARGV.OPTIONAL(bool): ["--noignore-properties", "--noignore", "--no-ignore-properties", "--no-ignore" "--all"],
        ARGV.OPTIONAL([str]): ["--ignore-properties", "--ignore"],
        ARGV.OPTIONAL(bool): ["--sort"],
        ARGV.OPTIONAL(int): ["--limit", "--count"],
        ARGV.OPTIONAL(int): ["--offset", "--skip", "--from"],
        ARGV.OPTIONAL(bool): ["--append"],
        ARGV.OPTIONAL(bool): ["--merge"],
        ARGV.OPTIONAL(bool): ["--overwrite"],
        ARGV.OPTIONAL(bool): ["--sid"],
        ARGV.OPTIONAL(bool): ["--show"],
        ARGV.OPTIONAL(bool): ["--nowarnings", "--nowarning", "--nowarn"],
        ARGV.OPTIONAL(bool): ["--verbose"],
        ARGV.OPTIONAL(bool): ["--debug"],
        ARGV.OPTIONAL(bool): ["--version"],
        ARGV.OPTIONAL(bool): ["--exceptions", "--exception", "--except"],
        ARGV.OPTIONAL(int, 50): ["--nthreads", "--threads"],
        ARGV.OPTIONAL(bool): ["--sanity-check", "--sanity"],
        ARGV.OPTIONAL(bool): ["--timing", "--time", "--times"],
        ARGV.OPTIONAL(bool): ["--noheader"],
        ARGV.OPTIONAL(bool): ["--argv"],
        ARGV.AT_MOST_ONE_OF: ["--inserts", "--raw"],
        ARGV.AT_MOST_ONE_OF: ["--inserts-files", "--raw"],
        ARGV.AT_MOST_ONE_OF: ["--metadata", "--nometadata"],
        ARGV.AT_LEAST_ONE_OF: ["--env", "--ini"],
        ARGV.DEPENDENCY: ["--no-ignore-properties", ARGV.DEPENDS_ON, ["--raw", "--inserts"]],
        ARGV.ALLOW_ONLY: ["--version"]
    })

    if argv.version:
        print(f"hms-portal-read: {get_version()}")

    _setup_debugging(argv)

    portal = _create_portal(env=argv.env, ini=argv.ini, app=argv.app,
                            exceptions=argv.exceptions, show=argv.show,
                            verbose=argv.verbose and not argv.noheader, debug=argv.debug)

    if argv.noignore_properties:
        portal.ignore_properties = []

    if argv.ignore_properties:
        portal.ignore_properties = argv.ignore_properties

    # By default use Portal.get_metadata, iff the given query argument does not start with a slash,
    # otherwise use Portal.get; override to use portal.get_metadata with the --metadata
    # option or override to use portal.get with the --nometadata option.
    metadata = (argv.metadata or (not argv.query.startswith("/"))) and (not argv.nometadata)

    if (not metadata) and (not argv.query.startswith("/")):
        argv.query = f"/{argv.query}"

    if items := _portal_get(portal, argv.query, metadata=metadata, raw=argv.raw, inserts=argv.inserts,
                            limit=argv.limit, offset=argv.offset, deleted=argv.deleted, nthreads=argv.nthreads):
        if graph := items.get("@graph"):
            items = graph
    if isinstance(items, dict):
        items = [items]

    if argv.refs:
        items.extend(_get_portal_referenced_items(
            portal, items, raw=argv.raw, metadata=argv.metadata,
            inserts=argv.inserts, database=argv.database, nthreads=argv.nthreads))

    if argv.inserts:
        items_by_type = {}
        for item in items:
            item_type = item.get(_ITEM_TYPE_PSEUDO_PROPERTY_NAME)
            if not (item_list := items_by_type.get(item_type)):
                items_by_type[item_type] = (item_list := [])
            item_list.append(item)
            item.pop(_ITEM_TYPE_PSEUDO_PROPERTY_NAME, None)
        items = items_by_type

    if argv.sort:
        items = sort_dictionary(items)

    if not argv.sid:
        _scrub_sids_from_items(items)

    if argv.output:
        if argv.inserts and (os.path.isdir(argv.output) or argv.output.endswith(os.sep)):
            _print_items_inserts(items, argv.output, noformat=argv.noformat,
                                 append=argv.append, overwrite=argv.overwrite, merge=argv.merge)
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

    if argv.refs and argv.sanity_check:
        _verbose("Sanity checking for missing referenced items ...", end="")
        if missing_items_referenced := _sanity_check_missing_items_referenced(items):
            _verbose("")
            _error(f"Missing items for referenced items found: {len(missing_items_referenced)}", exit=False)
            if argv.verbose:
                _verbose(missing_items_referenced)
        else:
            _verbose(f" OK {chars.check}")

    _verbose(f"Total fetched Portal items:"
             f" {len(get_uuids(items))} {chars.dot} references: {len(get_referenced_uuids(items))}")
    if argv.timing or argv.debug:
        _info(f"Calls to portal.get_metadata: {portal.get_metadata_call_count}"
              f" {chars.dot} {format_duration(portal.get_metadata_call_duration)}")
        _info(f"Calls to portal.get: {portal.get_call_count} {chars.dot} {format_duration(portal.get_call_duration)}")


def _print_items_inserts(items: dict, output_directory: str, noformat: bool = False,
                         append: bool = False, merge: bool = False, overwrite: bool = False) -> None:
    os.makedirs(output_directory, exist_ok=True)
    for item_type in items:
        item_type_items = items[item_type]
        output_file = os.path.join(output_directory, f"{to_snake_case(item_type)}.json")
        append_to_output_file = False
        merge_into_output_file = False
        overwriting_output_file = False
        if os.path.exists(output_file):
            if append:
                append_to_output_file = True
            elif merge:
                merge_into_output_file = True
            elif overwrite:
                overwriting_output_file = True
            else:
                _print(f"Specified output file already exists: {output_file} {chars.dot}")
                if not yes_or_no("Merge into this file?"):
                    if not yes_or_no("Overwrite this file?"):
                        if not yes_or_no("Append to this file?"):
                            continue
                        else:
                            append_to_output_file = True
                    else:
                        overwriting_output_file = True
                else:
                    merge_into_output_file = True
        if merge_into_output_file or append_to_output_file:
            try:
                with io.open(output_file, "r") as f:
                    if not isinstance(existing_items := json.load(f), list):
                        _warning(f"JSON file does not contain a list: {output_file}")
                        continue
                    if merge_into_output_file:
                        merge_identifying_property_name = "uuid"
                        for item in item_type_items:
                            if (i := _find_item(existing_items,
                                                property_value=item.get(merge_identifying_property_name),
                                                property_name=merge_identifying_property_name)) is not None:
                                existing_items[i] = item
                            else:
                                existing_items.append(item)
                    elif append_to_output_file:
                        existing_items.extend(item_type_items)
                    item_type_items = existing_items
            except Exception:
                _warning(f"Cannot load file as JSON: {output_file}")
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
    referenced_items = [] ; ignore_uuids = [] ; referenced_items_batch = item ; referenced_uuids_last = None  # noqa
    while referenced_uuids := get_referenced_uuids(referenced_items_batch, ignore_uuids=ignore_uuids,
                                                   exclude_uuid=True, include_paths=True):
        if (referenced_uuids := set(referenced_uuids)) == referenced_uuids_last:
            break
        referenced_uuids_last = referenced_uuids
        referenced_items_batch = _get_portal_items_for_uuids(
            portal, referenced_uuids, metadata=metadata, raw=raw, inserts=inserts, database=database, nthreads=nthreads)
        referenced_items.extend(referenced_items_batch)
        for item in referenced_items_batch:
            if item_uuid := item.get(_ITEM_UUID_PROPERTY_NAME):
                if item_uuid not in ignore_uuids:
                    ignore_uuids.append(item_uuid)
    return referenced_items


def _get_portal_items_for_uuids(portal: Portal, uuids: Union[List[str], Set[str], Tuple[str], str],
                                metadata: bool = False, raw: bool = False, inserts: bool = False,
                                database: bool = False, nthreads: Optional[int] = None) -> List[dict]:
    items = []
    if not isinstance(uuids, (list, set, tuple)):
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
    if inserts is True:
        items = _portal_get_inserts(portal, query, metadata=metadata, database=database,
                                    limit=limit, offset=offset, deleted=deleted, nthreads=nthreads)
    else:
        items = portal.GET(query, metadata=metadata, raw=raw,
                           database=database, limit=limit, offset=offset, deleted=deleted)
    return items


@lru_cache(maxsize=1024)
def _portal_get_inserts(portal: Portal, query: str, metadata: bool = False, database: bool = False,
                        limit: Optional[int] = None, offset: Optional[int] = None,
                        deleted: bool = False,
                        nthreads: Optional[int] = None) -> dict:
    item = None ; item_noraw = None  # noqa
    def fetch_portal_item() -> None:  # noqa
        nonlocal portal, query, database, item
        item = portal.GET(query, metadata=metadata, raw=True,
                          database=database, limit=limit, offset=offset, deleted=deleted)
    def fetch_portal_item_noraw() -> None:  # noqa
        # This is to get the non-raw frame item format which has the type information (the raw frame does not).
        nonlocal portal, query, metadata, database, item_noraw
        item_noraw = portal.GET(query, metadata=metadata, raw=False,
                                database=database, limit=limit, offset=offset, deleted=deleted,
                                field=_ITEM_UUID_PROPERTY_NAME)
    run_concurrently([fetch_portal_item, fetch_portal_item_noraw], nthreads=min(2, nthreads))
    if isinstance(graph := item.get("@graph"), list):
        if isinstance(item_noraw_graph := item_noraw.get("@graph"), list):
            def find_item_type(uuid: str) -> Optional[str]:
                nonlocal item_noraw, item_noraw_graph
                for item_element in item_noraw_graph:
                    if item_element.get(_ITEM_UUID_PROPERTY_NAME) == uuid:
                        return Portal.get_item_type(item_element)
                return None
            for graph_item in graph:
                if graph_item_type := find_item_type(graph_item.get(_ITEM_UUID_PROPERTY_NAME)):
                    graph_item[_ITEM_TYPE_PSEUDO_PROPERTY_NAME] = graph_item_type
    else:
        if item_type := Portal.get_item_type(item_noraw):
            item[_ITEM_TYPE_PSEUDO_PROPERTY_NAME] = item_type
    return item


def _find_item(items: List[dict], property_value: Any, property_name: Optional[str] = None) -> Optional[int]:
    """
    Finds the (first) dictionary in the given list whose "uuid" property (or the property named
    by the given property_name) value matches the given property_value and returns its list index,
    if found; if not found then returns None.
    """
    if isinstance(items, list) and (property_value is not None):
        if not (isinstance(property_name, str) and property_name):
            property_name = _ITEM_UUID_PROPERTY_NAME
        for i in range(len(items)):
            if isinstance(item := items[i], dict):
                if item.get(property_name) == property_value:
                    return i
    return None


def _scrub_sids_from_items(items: dict) -> None:
    if isinstance(items, list):
        for element in items:
            _scrub_sids_from_items(element)
    elif isinstance(items, dict):
        for key in list(items.keys()):
            if key == _ITEM_SID_PROPERTY_NAME:
                _warning(f"Deleting sid from item:"
                         f" {uuid if (uuid := items.get(_ITEM_UUID_PROPERTY_NAME)) else 'unknown'}")
                del items[key]
            else:
                _scrub_sids_from_items(items[key])


def _sanity_check_missing_items_referenced(data: Union[dict, list]) -> List[str]:
    missing_items_referenced = []
    for referenced_uuid in get_referenced_uuids(data):
        if not contains_uuid(data, referenced_uuid):
            missing_items_referenced.append(referenced_uuid)
    return missing_items_referenced


def _create_portal(env: Optional[str] = None, ini: Optional[str] = None, app: Optional[str] = None,
                   exceptions: bool = False, ping: bool = True, show: bool = False,
                   verbose: bool = False, debug: bool = False) -> Portal:
    portal = None ; error = None  # noqa
    with captured_output(not debug):
        try:
            if env or app:
                portal = Portal(env, app=app, exceptions=exceptions)
            else:
                portal = Portal(ini, exceptions=exceptions)
        except Exception as e:
            error = e
    if error:
        _error(str(error))
    if portal:
        if verbose:
            if portal.env:
                _info(f"Portal environment: {portal.env}")
            if portal.keys_file:
                _info(f"Portal keys file: {portal.keys_file}")
            if portal.key_id:
                if show:
                    _info(f"Portal key: {portal.key_id} {chars.dot} {portal.secret}")
                else:
                    _info(f"Portal key prefix: {portal.key_id[0:2]}******")
            if portal.ini_file:
                _info(f"Portal ini file: {portal.ini_file}")
            if portal.server:
                _info(f"Portal server: {portal.server}")
    if ping:
        if portal.ping():
            if verbose:
                _info(f"Portal connectivity: OK {chars.check}")
        else:
            _error(f"Portal connectivity: ERROR {chars.xmark}")
    return portal


def _print(*args, **kwargs) -> None:
    print(*args, **kwargs)


def _info(*args, **kwargs) -> None:
    _print(*args, **kwargs, file=sys.stderr, flush=True)


def _verbose(*args, **kwargs) -> None:
    _print(*args, **kwargs, file=sys.stderr, flush=True)


def _debug(message: str) -> None:
    _print(f"DEBUG: {message}", file=sys.stderr, flush=True)


def _warning(message: str) -> None:
    _print(f"WARNING: {message}", file=sys.stderr, flush=True)


def _error(message: str, exit: bool = True) -> None:
    print(f"ERROR: {message}", file=sys.stderr, flush=True)
    if exit is not False:
        sys.exit(1)


def _nofunction(*args, **kwargs) -> None:
    pass


def _setup_debugging(argv: ARGV) -> None:

    global _verbose, _debug, _nofunction
    if argv.nowarnings: _warning = _nofunction  # noqa
    if not argv.verbose: _verbose = _nofunction  # noqa
    if not argv.debug: _debug = _nofunction  # noqa

    original_requests_get = requests.get
    def requests_get(*args, **kwargs):  # noqa
        if isinstance(args, tuple) and (len(args) > 0):
            message = f"{args[0]}"
        else:
            message = str(args)
        if ((kwargs.get("headers", {}).get("Content-type") == "application/json") and
            (kwargs.get("headers", {}).get("Accept") == "application/json") and
            isinstance(auth := kwargs.get("auth"), tuple) and (len(auth) > 0) and (auth := auth[0])):  # noqa
            message += f" {chars.dot} stanard headers {chars.dot} key: {auth[0:2] + '******'}"
        else:
            message += f" {chars.dot} {str(kwargs)}"
        _debug(f"request.get: {message}")
        return original_requests_get(*args, **kwargs)
    requests.get = requests_get

    if argv.argv:
        _print(json.dumps(argv._dict, indent=4))


if __name__ == "__main__":
    main()
