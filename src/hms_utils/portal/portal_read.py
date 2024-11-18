from __future__ import annotations
from enum import Enum, auto as enum_auto
from functools import lru_cache
import io
import json
import os
import re
import requests
import sys
import time
from typing import Any, Callable, List, Optional, Set, Tuple, Union
import yaml
from dcicutils.command_utils import yes_or_no
from dcicutils.misc_utils import to_snake_case
from hms_utils.argv import ARGV
from hms_utils.chars import chars
from hms_utils.datetime_utils import format_duration
from hms_utils.dictionary_utils import contains_uuid, delete_properties_from_dictionaries, find_dictionary_item
from hms_utils.dictionary_utils import get_property, get_uuids, get_referenced_uuids, sort_dictionary
from hms_utils.portal.portal_utils import Portal as PortalFromUtils
from hms_utils.threading_utils import run_concurrently
from hms_utils.type_utils import is_uuid
from hms_utils.version_utils import get_version

_ITEM_SID_PROPERTY_NAME = "sid"
_ITEM_UUID_PROPERTY_NAME = "uuid"
_ITEM_TYPE_PSEUDO_PROPERTY_NAME = "@@@__TYPE__@@@"
_ITEM_IGNORE_REF_PROPERTIES = ["viewconfig", "higlass_uid", "blob_id"]


class Portal(PortalFromUtils):

    _ITEM_IGNORE_PROPERTIES_INSERTS = [
        "date_created",
        "last_modified",
        "schema_version",
        "submitted_by"
    ]

    class Access(Enum):
        OK = enum_auto()
        NOT_FOUND = enum_auto()
        NO_ACCESS = enum_auto()
        ERROR = enum_auto()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._get_call_count = 0
        self._get_metadata_call_count = 0
        self._get_call_duration = 0
        self._get_metadata_call_duration = 0
        self._raise_exception = kwargs.get("raise_exception") is True
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

    def GET(self, query: str, metadata: bool = False, raw: bool = False, database: bool = False,
            limit: Optional[int] = None, offset: Optional[int] = None,
            field: Optional[str] = None, deleted: bool = False,
            raise_exception: bool = False) -> Optional[Union[List[dict], dict]]:
        items = None
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
                                 limit=limit, offset=offset, deleted=deleted, field=field)
                if items.status_code == 404:
                    return Portal.Access.NOT_FOUND
                elif items.status_code == 403:
                    return Portal.Access.NO_ACCESS
                items = items.json()
                self._get_call_duration += time.time() - started
        except Exception as e:
            if (raise_exception is True) or self._raise_exception:
                raise
            return Portal._get_access_status(e)
        if self._ignore_properties and items:
            delete_properties_from_dictionaries(items, self._ignore_properties)
        return items

    def access(self, query: str, metadata: bool = False, raw: bool = False, inserts: bool = False,
               report: bool = False, printf: Optional[Callable] = None) -> Portal.Access:
        access = Portal.Access.OK
        try:
            self.GET(query, metadata=metadata, raw=raw or inserts, raise_exception=True)
        except Exception as e:
            access = Portal._get_access_status(e)
        if report is True:
            Portal.report_access_status(access, query=query, verbose=False)
        return access

    @staticmethod
    def _get_access_status(e: Optional[Exception]) -> Access:
        # TODO
        # Bad status code for GET request for http://localhost:8000/a7ca8dab-b1f0-4f61-a892-87fe3516830a:
        # 403. Reason: {'@type': ['HTTPForbidden', 'Error'], 'status': 'error',
        # 'code': 403, 'title': 'Forbidden', 'description': 'Access was denied to this resource.',
        # 'detail': 'Unauthorized: item_view failed permission check'}
        # VS.
        # Bad status code for GET request for http://localhost:8000/a7ca8dab-b1f0-4f61-a892-87fe3516830aasfd:
        # 404. Reason: {\'@type\': [\'HTTPNotFound\', \'Error\'], \'status\': \'error\',
        # \'code\': 404, \'title\': \'Not Found\', \'description\':
        # \'The resource could not be found.\', \'detail\':
        # "debug_notfound of url http://localhost:8000/a7ca8dab-b1f0-4f61-a892-87fe3516830aasfd; path_info:
        # \'/a7ca8dab-b1f0-4f61-a892-87fe3516830aasfd\', context: <encoded.root.SMAHTRoot object at 0x1371d39b0>,
        # view_name: \'a7ca8dab-b1f0-4f61-a892-87fe3516830aasfd\', subpath: (), traversed: (),
        # root: <encoded.root.SMAHTRoot object at 0x1371d39b0>,
        # vroot: <encoded.root.SMAHTRoot object at 0x1371d39b0>, vroot_path: ()"}'
        def contains_word(text: str, word: str) -> bool:  # noqa
            return bool(re.search(rf"\b{word}\b", text, re.IGNORECASE))
        if isinstance(e, Exception):
            if (contains_word(e := str(e), "HTTPForbidden") or
                contains_word(e, "forbidden") or contains_word(e, "unauthorized")):  # noqa
                access = Portal.Access.NO_ACCESS
            elif contains_word(e, "HTTPNotFound") or (contains_word(e, "found") and
                                                      contains_word(e, "not") and contains_word(e, "404")):
                access = Portal.Access.NOT_FOUND
            else:
                access = Portal.Access.ERROR
        else:
            access = Portal.Access.OK
        return access

    @staticmethod
    def report_access_status(access: Portal.Access,
                             query: Optional[str] = None, verbose: bool = False,
                             printf: Optional[Callable] = None) -> None:
        if not callable(printf):
            printf = print
        if access == Portal.Access.NOT_FOUND:
            if verbose is True:
                printf(f"Portal items(s) not found{f': {query}' if query else '.'}")
            else:
                printf(f"{f'{query}: ' if query else ''}Not found")
        elif access == Portal.Access.NO_ACCESS:
            if verbose is True:
                printf(f"Forbidden access to Portal item(s){f': {query}' if query else '.'}")
            else:
                printf(f"{f'{query}: ' if query else ''}Forbidden")
        elif access == Portal.Access.ERROR:
            if verbose is True:
                printf(f"Error retrieving Portal item(s){f': {query}' if query else ''}")
            else:
                printf(f"{f'{query}: ' if query else ''}Error")
        elif access == Portal.Access.OK:
            printf(f"{query}: OK")
        else:
            if verbose is True:
                printf(f"Unknown error retrieving Portal item(s){f': {query}' if query else ''}")
            else:
                printf(f"{f'{query}: ' if query else ''}Unknown error")


def main() -> int:

    started = time.time()

    argv = ARGV({
        ARGV.OPTIONAL(str): ["query"],
        ARGV.OPTIONAL(bool): ["--ping"],
        ARGV.OPTIONAL(bool): ["--version"],
        ARGV.AT_LEAST_ONE_OF: ["query", "--ping", "--version"],
        ARGV.OPTIONAL(str): ["--app"],
        ARGV.OPTIONAL(str): ["--env", "--e"],
        ARGV.OPTIONAL(str): ["--ini", "--ini-file"],
        ARGV.OPTIONAL(bool): ["--inserts", "--insert"],
        ARGV.OPTIONAL(str): ["--output", "--out", "--o"],
        ARGV.OPTIONAL(bool): ["--check-access-only", "--check-access", "--check", "--access"],
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
        ARGV.OPTIONAL(bool): ["--uuids"],
        ARGV.OPTIONAL([str]): ["--pick"],
        ARGV.OPTIONAL(str): ["--pick-separator", "--pick-sep"],
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
        ARGV.OPTIONAL(int, 50): ["--nthreads", "--threads"],
        ARGV.OPTIONAL(bool): ["--sanity-check", "--sanity"],
        ARGV.OPTIONAL(bool): ["--timing", "--time", "--times"],
        ARGV.OPTIONAL(bool): ["--noheader"],
        ARGV.OPTIONAL(str): ["--conflicts", "--conflict"],
        ARGV.OPTIONAL(bool): ["--argv"],
        ARGV.AT_MOST_ONE_OF: ["--inserts", "--raw"],
        ARGV.AT_MOST_ONE_OF: ["--inserts-files", "--raw"],
        ARGV.AT_MOST_ONE_OF: ["--metadata", "--nometadata"],
        ARGV.OPTIONAL(bool): ["--exceptions", "--exception", "--except"],
        ARGV.DEPENDENCY: ["--no-ignore-properties", ARGV.DEPENDS_ON, ["--raw", "--inserts"]],
    })

    _setup_debugging(argv)

    if argv.version:
        print(f"hms-portal-read: {get_version()}")

    if not (portal := Portal.create(argv.env or argv.ini, app=argv.app, show=argv.show,
                                    verbose=argv.verbose and not argv.noheader, debug=argv.debug,
                                    ping=argv.ping, raise_exception=argv.exceptions, printf=_info)):
        return 1

    if not argv.query:
        return 0

    if ("/" not in argv.query) and ("-" not in argv.query) and (schema := portal.get_schema(argv.query)):
        _write_data(schema, argv)
        return 0

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

    _verbose(f"Querying Portal for item(s): {argv.query}")

    if argv.check_access_only:
        return 0 if portal.access(argv.query, metadata=metadata, raw=argv.raw, inserts=argv.inserts,
                                  report=True, printf=_print) == Portal.Access.OK else 1

    items = _portal_get(portal, argv.query, metadata=metadata, raw=argv.raw, inserts=argv.inserts,
                        limit=argv.limit, offset=argv.offset, database=argv.database,
                        deleted=argv.deleted, nthreads=argv.nthreads)
    if isinstance(items, Portal.Access):
        portal.report_access_status(items, query=argv.query, verbose=True)
        return 1

    if graph := items.get("@graph"):
        items = graph
    if isinstance(items, dict):
        items = [items]

    if argv.refs:
        items.extend(_get_portal_referenced_items(
            portal, items, raw=argv.raw, metadata=argv.metadata,
            inserts=argv.inserts, database=argv.database, nthreads=argv.nthreads))

    if argv.inserts:
        items = _insertize_items(items)

    if argv.sort:
        items = sort_dictionary(items)

    if not argv.sid:
        _scrub_sids_from_items(items)

    if argv.conflicts:
        if not (portal_compare := Portal.create(argv.conflicts)):
            _error(f"Cannot access portal for conflict checks: {argv.conflicts}")
        if (conflicts := conflicts_exist(portal, items, portal_compare=portal_compare)):
            _print("CONFLICTS:")
            _print(json.dumps(conflicts, indent=4))
        else:
            _print("No conflcts.")

    elif argv.uuids or argv.pick:
        if argv.pick:
            if _ITEM_UUID_PROPERTY_NAME not in argv.pick:
                argv.pick.insert(0, _ITEM_UUID_PROPERTY_NAME)
        else:
            argv.pick = [_ITEM_UUID_PROPERTY_NAME]
        if argv.pick_separator:
            if argv.pick_separator in ["\\t", "tab", "TAB"]:
                argv.pick_separator = "\t"
        def write_item_properties(items: List[dit], names: List[str],  # noqa
                                  write: Callable, separator: Optional[str] = None) -> None:
            if isinstance(items, list) and isinstance(names, list) and callable(write):
                if not isinstance(separator, str):
                    separator = " "
                for item in items:
                    values = []
                    for name in names:
                        if value := get_property(item, name):
                            values.append(str(value))
                    write(separator.join(values))
        if not isinstance(items, list):
            _error("Result set if not a list of items which is required when using the --uuids option.")
        if argv.output:
            if os.path.isdir(argv.output):
                _error(f"Specified output file already exists as a directory: {argv.output}")
            elif os.path.exists(argv.output):
                if (not argv.append) and (argv.overwrite or yes_or_no("Overwrite this file?")):
                    with io.open(argv.output, "w") as f:
                        write_item_properties(items, argv.pick,
                                              write=lambda value: f.write(f"{value}\n"), separator=argv.pick_separator)
                elif argv.append or yes_or_no("Append to this file?"):
                    with io.open(argv.output, "a") as f:
                        write_item_properties(items, argv.pick,
                                              write=lambda value: f.write(f"{value}\n"), separator=argv.pick_separator)
                else:
                    return 1
        else:
            write_item_properties(items, argv.pick, write=print, separator=argv.pick_separator)
        return 0

    elif argv.output:
        if argv.inserts and (os.path.isdir(argv.output) or argv.output.endswith(os.sep)):
            _write_inserts_output_files(items, argv.output, noformat=argv.noformat,
                                        overwrite=argv.overwrite, merge=argv.merge, append=argv.append)
        else:
            _write_output_file(items, argv.output, inserts=argv.inserts, noformat=argv.noformat,
                               overwrite=argv.overwrite, merge=argv.merge, append=argv.append)

    else:
        _write_data(items, argv)

    if argv.refs and argv.sanity_check:
        _verbose("Sanity checking for missing referenced items ...", end="")
        started_sanity_check = time.time()
        missing_items_referenced = _sanity_check_missing_items_referenced(items)
        duration_sanity_check = format_duration(time.time() - started_sanity_check)
        if missing_items_referenced:
            _verbose(f" {duration_sanity_check}" if duration_sanity_check != "00:0000" else "")
            _error(f"Missing items for referenced items found: {len(missing_items_referenced)}", exit=False)
            if argv.verbose:
                _verbose(missing_items_referenced)
        else:
            _verbose(f" OK {chars.check}{f' {duration_sanity_check}' if duration_sanity_check != '00:00:00' else ''}")

    if argv.verbose:
        uuids_count = len(get_uuids(items))
        referenced_uuids_count = len(get_referenced_uuids(items, exclude_properties=_ITEM_IGNORE_REF_PROPERTIES))
        _verbose(f"Total items fetched:"
                 f" {uuids_count}"
                 f"{f' {chars.dot} refs: {referenced_uuids_count}' if referenced_uuids_count != uuids_count else ''}")
        if argv.verbose and argv.inserts and isinstance(items, dict):
            type_count = len(set(items.keys()))
            _verbose(f"Total item types fetched: {type_count}")
    if argv.timing or argv.debug:
        _info(f"Calls to portal.get_metadata: {portal.get_metadata_call_count}"
              f" {chars.dot} {format_duration(portal.get_metadata_call_duration)}")
        _info(f"Calls to portal.get: {portal.get_call_count} {chars.dot} {format_duration(portal.get_call_duration)}")
    if argv.verbose or argv.timing or argv.debug:
        duration = time.time() - started
        _info(f"Duration: {format_duration(duration)}")
    return 0


def _write_inserts_output_files(items: dict, output_directory: str, noformat: bool = False,
                                overwrite: bool = False, merge: bool = False, append: bool = False) -> None:
    os.makedirs(output_directory, exist_ok=True)
    for item_type in items:
        item_type_items = items[item_type]
        output_file = os.path.join(output_directory, f"{to_snake_case(item_type)}.json")
        overwrite_output_file = False
        merge_into_output_file = False
        append_to_output_file = False
        if os.path.exists(output_file):
            if overwrite:
                overwrite_output_file = True
            elif merge:
                merge_into_output_file = True
            elif append:
                append_to_output_file = True
            else:
                _print(f"Specified output file already exists: {output_file} {chars.dot}")
                if not yes_or_no("Merge into this file?"):
                    if not yes_or_no("Overwrite this file?"):
                        if not yes_or_no("Append to this file?"):
                            continue
                        append_to_output_file = True
                    else:
                        overwrite_output_file = True
                else:
                    merge_into_output_file = True
            if merge_into_output_file or append_to_output_file:
                try:
                    with io.open(output_file, "r") as f:
                        if not isinstance(existing_items := json.load(f), list):
                            _warning(f"JSON file does not contain a list: {output_file}")
                            continue
                except Exception:
                    _warning(f"Cannot load file as JSON: {output_file}")
                    continue
                if merge_into_output_file:
                    merge_identifying_property_name = _ITEM_UUID_PROPERTY_NAME
                    for item in item_type_items:
                        index = find_dictionary_item(existing_items,
                                                     property_value=item.get(merge_identifying_property_name),
                                                     property_name=merge_identifying_property_name)
                        if index is not None:
                            existing_items[index] = item
                        else:
                            existing_items.append(item)
                elif append_to_output_file:
                    existing_items.extend(item_type_items)
                item_type_items = existing_items
        with io.open(output_file, "w") as f:
            if overwrite_output_file:
                _debug(f"Overwriting output file: {output_file}")
            elif merge_into_output_file:
                _debug(f"Merging into output file: {output_file}")
            else:
                _debug(f"Writing output file: {output_file}")
            json.dump(item_type_items, f, indent=None if (noformat is True) else 4)
            if overwrite_output_file:
                _verbose(f"Output file overwritten: {output_file}")
            elif merge_into_output_file:
                _verbose(f"Output file merged into: {output_file}")
            elif append_to_output_file:
                _verbose(f"Output file appended to: {output_file}")
            else:
                _verbose(f"Output file written: {output_file}")


def _write_output_file(items: dict, output_file: str, inserts: bool = False, noformat: bool = False,
                       overwrite: bool = False, merge: bool = False, append: bool = False) -> None:
    overwrite_output_file = False
    merge_into_output_file = False
    append_to_output_file = False
    if os.path.isdir(output_file):
        _error(f"Specified output file already exists as a directory: {output_file}")
    if os.path.exists(output_file):
        if overwrite:
            overwrite_output_file = True
        elif merge:
            merge_into_output_file = True
        elif append:
            append_to_output_file = True
        else:
            _print(f"Specified output file already exists: {output_file}")
            if not yes_or_no("Merge into this file?"):
                if not yes_or_no("Overwrite this file?"):
                    if not yes_or_no("Append to this file?"):
                        return 1
                    append_to_output_file = True
                else:
                    overwrite_output_file = True
            else:
                merge_into_output_file = True
        if merge_into_output_file or append_to_output_file:
            try:
                with io.open(output_file, "r") as f:
                    existing_items = json.load(f)
                    if inserts:
                        if not isinstance(existing_items, dict):
                            _error(f"JSON file does not contain a dictionary: {output_file}")
                    elif not isinstance(existing_items, list):
                        _error(f"JSON file does not contain a list: {output_file}")
            except Exception:
                _error(f"Cannot load file as JSON: {output_file}")
            if merge_into_output_file:
                merge_identifying_property_name = _ITEM_UUID_PROPERTY_NAME
                if inserts:
                    for item_type in items:
                        if existing_item_type_items := existing_items.get(item_type):
                            if isinstance(existing_item_type_items, list):
                                for item in items[item_type]:
                                    index = find_dictionary_item(
                                        existing_item_type_items,
                                        property_value=item.get(merge_identifying_property_name),
                                        property_name=merge_identifying_property_name)
                                    if index is not None:
                                        existing_item_type_items[index] = item
                                    else:
                                        existing_item_type_items.append(item)
                        else:
                            existing_items[item_type] = items[item_type]
                else:
                    for item in items:
                        index = find_dictionary_item(
                            existing_items,
                            property_value=item.get(merge_identifying_property_name),
                            property_name=merge_identifying_property_name)
                        if index is not None:
                            existing_items[index] = item
                        else:
                            existing_items.append(item)
            elif append_to_output_file:
                if inserts:
                    for item_type in items:
                        if existing_item_type_items := existing_items.get(item_type):
                            if isinstance(existing_item_type_items, list):
                                existing_item_type_items.append(items[item_type])
                        else:
                            existing_items[item_type] = items[item_type]
                else:
                    existing_items.extend(items)
            items = existing_items
    with io.open(output_file, "w") as f:
        json.dump(items, f, indent=None if noformat else 4)
    if overwrite_output_file:
        _verbose(f"Output file overwritten: {output_file}")
    elif merge_into_output_file:
        _verbose(f"Output file merged into: {output_file}")
    elif append_to_output_file:
        _verbose(f"Output file appended to: {output_file}")
    else:
        _verbose(f"Output file written: {output_file}")


def _write_data(data: Any, argv: ARGV) -> None:
    if argv.yaml is True:
        _print(yaml.dump(data).strip())
    elif argv.noformat is True:
        _print(data)
    else:
        _print(json.dumps(data, indent=4))


def _get_portal_referenced_items(portal: Portal, item: dict, metadata: bool = False,
                                 raw: bool = False, inserts: bool = False, database: bool = False,
                                 nthreads: Optional[int] = None) -> List[dict]:
    referenced_items = [] ; ignore_uuids = [] ; referenced_items_batch = item ; referenced_uuids_last = None  # noqa
    while referenced_uuids := get_referenced_uuids(referenced_items_batch, ignore_uuids=ignore_uuids,
                                                   exclude_uuid=True, include_paths=True,
                                                   exclude_properties=_ITEM_IGNORE_REF_PROPERTIES):
        if (referenced_uuids := set(referenced_uuids)) == referenced_uuids_last:
            break
        referenced_uuids_last = referenced_uuids
        referenced_items_batch = _get_portal_items_for_uuids(
            portal, referenced_uuids, metadata=metadata, raw=raw, inserts=inserts, database=database, nthreads=nthreads)
        for referenced_item in referenced_items_batch:
            if isinstance(referenced_item, dict):
                referenced_items.append(referenced_item)
        for item in referenced_items_batch:
            if isinstance(item, dict):
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
            if not isinstance(item, dict):
                print(f"XYZZY[{uuid}]", file=sys.stderr)
                print(item, file=sys.stderr)
            items.append(item)  # TODO: make thread-safe.
    if fetch_portal_item_functions := [lambda uuid=uuid: fetch_portal_item(uuid) for uuid in uuids if is_uuid(uuid)]:
        run_concurrently(fetch_portal_item_functions, nthreads=nthreads)
    return items


@lru_cache(maxsize=1024)
def _portal_get(portal: Portal, query: str, metadata: bool = False, raw: bool = False,
                inserts: bool = False, database: bool = False,
                limit: Optional[int] = None, offset: Optional[int] = None, deleted: bool = False,
                nthreads: Optional[int] = None) -> dict:
    if inserts is True:
        return _portal_get_inserts(portal, query, metadata=metadata, database=database,
                                   limit=limit, offset=offset, deleted=deleted, nthreads=nthreads)
    return portal.GET(query, metadata=metadata, raw=raw,
                      database=database, limit=limit, offset=offset, deleted=deleted)


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
    if not item:
        return {}
    elif item in [Portal.Access.NOT_FOUND, Portal.Access.NO_ACCESS, Portal.Access.ERROR]:
        return item
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


def _insertize_items(items: dict) -> dict:
    items_by_type = {}
    for item in items:
        if isinstance(item, dict):
            item_type = item.get(_ITEM_TYPE_PSEUDO_PROPERTY_NAME)
            if not (item_list := items_by_type.get(item_type)):
                items_by_type[item_type] = (item_list := [])
            item_list.append(item)
            item.pop(_ITEM_TYPE_PSEUDO_PROPERTY_NAME, None)
    return items_by_type


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
    for referenced_uuid in get_referenced_uuids(data, exclude_properties=_ITEM_IGNORE_REF_PROPERTIES):
        if not contains_uuid(data, referenced_uuid):
            missing_items_referenced.append(referenced_uuid)
    return missing_items_referenced


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
            message += f" {chars.dot} standard headers {chars.dot} key: {auth[0:2] + '******'}"
        else:
            message += f" {chars.dot} {str(kwargs)}"
        _debug(f"request.get: {message}")
        return original_requests_get(*args, **kwargs)
    requests.get = requests_get

    if argv.argv:
        _print(json.dumps(argv._dict, indent=4))


def conflicts_exist(portal_source: Portal, items: dict, portal_compare: Optional[Portal] = None) -> List[dict]:
    conflicts = []
    for item_type in items:
        for item in items[item_type]:
            if item_conflicts := conflict_exists(portal_source, item, item_type, portal_compare):
                conflicts.extend(item_conflicts)
    return conflicts


def conflict_exists(portal_source: Portal, item: dict, item_type: Optional[str] = None,
                    portal_compare: Optional[Portal] = None) -> List[dict]:
    conflicts = []

    def get_item_from_portal(item_type: str, identifying_property: str, identifying_value: Any) -> Optional[dict]:
        return portal_compare.get_metadata(f"/{item_type}/{identifying_value}", raw=True, raise_exception=False)

    def get_item_from_file_system(item_type: str, identifying_property: str, identifying_value: Any) -> Optional[dict]:
        return None  # TODO

    if isinstance(portal_compare, Portal):
        get_existing_item = get_item_from_portal
        existing_source = portal_compare.env
        existing_source_property_name = "directory"
    elif isinstance(portal_compare, str) and os.path.isdir(portal_compare):
        get_existing_item = get_item_from_file_system
        existing_source = portal_compare
        existing_source_property_name = "portal"
    else:
        return conflicts

    identifying_properties = portal_source.get_identifying_property_names(item_type)
    item_uuid = item.get(_ITEM_UUID_PROPERTY_NAME)

    for identifying_property in identifying_properties:
        if (identifying_value := item.get(identifying_property)) is not None:
            if (existing_item := get_existing_item(item_type, identifying_property, identifying_value)) is not None:
                if existing_item.get(_ITEM_UUID_PROPERTY_NAME) != item_uuid:
                    conflicts.append({
                        "conflict": {
                            "identifying_property": identifying_property,
                            "identifying_value": identifying_value,
                            "retrieved": {
                                "portal": portal_source.env,
                                "uuid": item_uuid,
                                "item": item
                            },
                            "existing": {
                                "portal": existing_source,
                                "uuid": existing_item.get(_ITEM_UUID_PROPERTY_NAME),
                                "item": existing_item
                            }
                        }
                    })

    if (existing_item := get_existing_item(item_type, _ITEM_UUID_PROPERTY_NAME, item_uuid)) is not None:
        for identifying_property in identifying_properties:
            if existing_item.get(identifying_property) != item.get(identifying_property):
                conflicts.append({
                    "conflict": {
                        "uuid": item_uuid,
                        "identifying_property": identifying_property,
                        "retrieved": {
                            "portal": portal_source.env,
                            "identifying_value": item.get(identifying_property),
                            "item": item
                        },
                        "existing": {
                            existing_source_property_name: existing_source,
                            "identifying_value": existing_item.get(identifying_property),
                            "item": existing_item
                        }
                    }
                })

    return conflicts


if __name__ == "__main__":
    status = main()
    sys.exit(status if isinstance(status, int) else 0)
