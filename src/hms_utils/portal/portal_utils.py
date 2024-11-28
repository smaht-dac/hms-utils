from __future__ import annotations
import os
import sys
from typing import Callable, List, Optional, Union
from dcicutils.captured_output import captured_output
from hms_utils.dictionary_utils import get_properties
from dcicutils.portal_utils import Portal as PortalFromUtils
from dcicutils.ff_utils import delete_field, delete_metadata, purge_metadata
from dcicutils.common import APP_SMAHT, ORCHESTRATED_APPS
from hms_utils.chars import chars
from hms_utils.type_utils import is_uuid, to_non_empty_string_list


class Portal(PortalFromUtils):

    def delete_metadata(self, object_id: str) -> Optional[dict]:
        if self.key:
            return delete_metadata(obj_id=object_id, key=self.key)
        return None

    def purge_metadata(self, object_id: str) -> Optional[dict]:
        if self.key:
            return purge_metadata(obj_id=object_id, key=self.key)
        return None

    def delete_metadata_property(self, item_path: str, property_name: str, raise_exception: bool = False) -> bool:
        try:
            delete_field(item_path, property_name, key=self.key)
            return True
        except Exception as e:
            if raise_exception is True:
                raise e
        return False

    def reindex_metadata(self, uuids: Union[List[str], str], raise_exception: bool = False) -> bool:
        if isinstance(uuids, str) and is_uuid(uuids):
            uuids = [uuids]
        elif isinstance(uuids, list):
            if not (uuids := [uuid for uuid in uuids if is_uuid(uuid)]):
                return False
        else:
            return False
        try:
            return self.post("/queue_indexing", json={"uuids": uuids}).status_code == 200
        except Exception as e:
            if raise_exception is True:
                raise e
            return False

    @staticmethod
    def get_item_type(item: dict) -> Optional[str]:
        if isinstance(item, dict):
            if isinstance(item_types := item.get("@type"), list):
                return item_types[0] if (item_types := to_non_empty_string_list(item_types)) else None
            return item_types if isinstance(item_types, str) and item_types else None
        return None

    @classmethod
    def create(cls,
               arg: Optional[str] = None,
               app: Optional[str] = None,
               raise_exception: bool = False,
               verbose: bool = False,
               debug: bool = False,
               noerror: bool = False,
               ping: bool = False,
               noping: bool = False,
               show: bool = False,
               printf: Optional[Callable] = None, **kwargs) -> Portal:

        env_environ_name = None
        if not (isinstance(arg, str) and arg):
            if isinstance(app, str) and app and (app in ORCHESTRATED_APPS):
                env_app_name = app
            else:
                env_app_name = APP_SMAHT
            env_environ_name = f"{env_app_name.upper()}_ENV"
            if not (arg := os.environ.get(env_environ_name)):
                env_environ_name = None

        if not callable(printf):
            printf = lambda *args, **kwargs: print(*args, **kwargs, file=sys.stderr)  # noqa

        if ping:
            verbose = True

        with captured_output(debug is not True):
            try:
                portal = cls(arg, app=app, raise_exception=raise_exception, **kwargs)
            except Exception as e:
                if raise_exception is True:
                    raise
                if (verbose is True) or (noerror is not True):
                    printf(f"ERROR: {str(e)}")
                return None

        if verbose is True:
            if portal.env:
                if env_environ_name:
                    printf(f"Portal environment: {portal.env}"
                           f" {chars.dot} from environment variable: {env_environ_name}")
                else:
                    printf(f"Portal environment: {portal.env}")
            if portal.keys_file:
                printf(f"Portal keys file: {portal.keys_file}")
            if portal.key_id:
                if show is True:
                    printf(f"Portal key: {portal.key_id} {chars.dot} {portal.secret}")
                else:
                    printf(f"Portal key prefix: {portal.key_id[0:2]}******")
            if portal.ini_file:
                printf(f"Portal ini file: {portal.ini_file}")
            if portal.server:
                printf(f"Portal server: {portal.server}")
        if noping is not True:
            status = 0
            if portal.ping():
                if verbose:
                    version = None
                    bluegreen = None
                    try:
                        # SMaHT only just for BTW/FYI ...
                        health = portal.get_health().json()
                        version = health.get("project_version")
                        if (beanstalk_env := health.get("beanstalk_env")) == "smaht-production-green":
                            bluegreen = "green"
                        elif beanstalk_env == "smaht-production-blue":
                            bluegreen = "blue"
                    except Exception:
                        pass
                    printf(f"Portal connectivity: OK {chars.dot}{f' {version}' if version else ''}"
                           f"{f' {chars.dot} {bluegreen}' if bluegreen else ''} {chars.check}")
            else:
                printf(f"Portal connectivity: {portal.server} ({portal.env}) is unreachable {chars.xmark}")
                return None
            if ping is True:
                exit(status)

        return portal


def select_items(items: List[dict], predicate: Callable) -> List[dict]:
    if not (isinstance(items, list) and items):
        return []
    return [item for item in items if predicate(item)]


def group_items_by(items: list[dict], grouping: str,
                   identifying_property: Optional[str] = None, raw: bool = False) -> dict:
    if not (isinstance(items, list) and items and isinstance(grouping, str) and grouping):
        return {}
    if not (isinstance(identifying_property, str) and identifying_property):
        identifying_property = None
    results = {None: []}  # To make sure None is the first one for convenience; delete later of no None.
    for item in items:
        if identifying_property and ((identifying_value := item.get(identifying_property)) is not None):
            item_identity = identifying_value
        else:
            item_identity = item
        if grouping_values := get_properties(item, grouping):
            for grouping_value in grouping_values:
                if results.get(grouping_value) is None:
                    results[grouping_value] = []
                results[grouping_value].append(item_identity)
        else:
            results[None].append(item_identity)
    if not results[None]:
        del results[None]
    if (raw is True) or (not results):
        return results
    return {
        "group": grouping,
        "item_count": len(items),
        "group_count": len(results),
        "group_items": results
    }


def group_items_by_groupings(items: list[dict], groupings: List[str],
                             identifying_property: Optional[str] = None) -> dict:
    if not (isinstance(items, list) and items):
        return {}
    if isinstance(groupings, str) and groupings:
        groupings = [groupings]
    elif not (isinstance(groupings, list) and groupings):
        return {}
    if not (isinstance(identifying_property, str) and identifying_property):
        identifying_property = None
    main_grouped_items = None
    grouped_items = None
    for grouping in groupings:
        if main_grouped_items is None:
            if not (main_grouped_items := group_items_by(items, grouping, identifying_property=identifying_property)):
                break
            grouped_items = main_grouped_items
            continue
        for grouped_item_key in (group_items := grouped_items["group_items"]):
            grouped_items = group_items_by(
                select_items(items, lambda item: item.get(identifying_property) in group_items[grouped_item_key]),
                grouping, identifying_property=identifying_property)
            group_items[grouped_item_key] = grouped_items
    return main_grouped_items


def print_grouped_items(grouped_items: dict, indent: Optional[int] = None, display_item_count: bool = False) -> None:
    if not (isinstance(indent, int) and (indent > 0)):
        indent = 0
    spaces = (" " * indent) if indent > 0 else ""
    group = grouped_items["group"]
    group_count = grouped_items["group_count"]
    item_count = grouped_items["item_count"]
    group_items = grouped_items["group_items"]
    message = f"{spaces}{chars.diamond} GROUP: {group} ({group_count})"
    if display_item_count is True:
        message += f" {chars.dot} items: {item_count}"
    print(message)
    for group_item_key in group_items:
        grouped_items = group_items[group_item_key]
        message = (f"{spaces}  {chars.rarrow if indent == 0 else chars.rarrow_hollow}"
                   f" {group_item_key if group_item_key is not None else chars.null}")
        if isinstance(grouped_items, dict):
            if isinstance(grouped_items_count := grouped_items.get("item_count"), int):
                message += f" ({grouped_items_count})"
            print(message)
            print_grouped_items(grouped_items, indent=indent+4)
        elif isinstance(grouped_items, list):
            print(f"{message} ({len(grouped_items)})")
            for grouped_item in grouped_items:
                print(f"{spaces}    {chars.dot} {grouped_item}")
