from __future__ import annotations
from typing import Callable, List, Optional, Union
from dcicutils.captured_output import captured_output
from hms_utils.chars import chars
from dcicutils.portal_utils import Portal as PortalFromUtils
from dcicutils.ff_utils import delete_field, delete_metadata, purge_metadata
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
               env: Optional[str] = None,
               ini: Optional[str] = None,
               app: Optional[str] = None,
               raise_exception: bool = False,
               ping: bool = True,
               verbose: bool = False,
               debug: bool = False,
               show: bool = False,
               printf: Optional[Callable] = None, **kwargs) -> Portal:

        if not callable(printf):
            printf = print

        with captured_output(debug is not True):
            try:
                portal = cls(ini or env, app=app, raise_exception=raise_exception, **kwargs)
            except Exception as e:
                if raise_exception is True:
                    raise
                if verbose is True:
                    printf(f"ERROR: {str(e)}")
                return None

        if verbose is True:
            if portal.env:
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
        if ping is not False:
            if portal.ping():
                if verbose:
                    version = None
                    bluegreen = None
                    try:
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
                printf(f"Portal connectivity: {portal.server} is unreachable {chars.xmark}")

        return portal
