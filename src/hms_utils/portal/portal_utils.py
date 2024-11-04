from typing import List, Optional, Union
from dcicutils.portal_utils import Portal as PortalFromUtils
from dcicutils.ff_utils import delete_field, delete_metadata, purge_metadata
from hms_utils.type_utils import is_uuid


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
