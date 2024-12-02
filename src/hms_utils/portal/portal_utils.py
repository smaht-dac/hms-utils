from __future__ import annotations
import os
import pyramid
import sys
import webtest
from typing import Callable, List, Optional, Union
from webob.multidict import MultiDict
from dcicutils.captured_output import captured_output
from dcicutils.portal_utils import Portal as PortalFromUtils
from dcicutils.ff_utils import delete_field, delete_metadata, purge_metadata
from dcicutils.common import APP_SMAHT, ORCHESTRATED_APPS
from hms_utils.chars import chars
from hms_utils.type_utils import is_uuid, to_non_empty_string_list


class Portal(PortalFromUtils):

    def get_metadata(self, object_id: str, raw: bool = False, database: bool = False,
                     limit: Optional[int] = None, offset: Optional[int] = None,
                     field: Optional[str] = None, deleted: bool = False,
                     raise_exception: bool = True) -> Optional[dict]:
        if isinstance(object_id, str):
            object_id = object_id.lstrip("/")
        return super().get_metadata(object_id, raw, database, limit, offset, field, deleted, raise_exception)

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


class PyramidRequestForTesting(pyramid.request.Request):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._params = None
        self.vapp = None
    @property  # noqa
    def params(self) -> MultiDict:
        if self._params is not None:
            return self._params
        return super().params
    @params.setter  # noqa
    def params(self, value: MultiDict) -> None:
        if not isinstance(value, MultiDict):
            raise Exception("Must set pyramid.request.Request.params to MultiDict.")
        self._params = value


def create_pyramid_request_for_testing(
        portal_or_vapp_or_request: Union[PortalFromUtils, webtest.app.TestApp],
        args: Optional[Union[str, dict]] = None) -> Optional[pyramid.request.Request]:
    if not isinstance(vapp := portal_or_vapp_or_request, webtest.app.TestApp):
        if not (isinstance(portal_or_vapp_or_request, PortalFromUtils) and
                isinstance(vapp := portal_or_vapp_or_request.vapp, webtest.app.TestApp)):
            if not (isinstance(portal_or_vapp_or_request, PyramidRequestForTesting) and
                    isinstance(vapp := portal_or_vapp_or_request.vapp, webtest.app.TestApp)):
                return None
    if not isinstance(router := vapp.app, pyramid.router.Router):
        return None
    if not isinstance(registry := router.registry, pyramid.registry.Registry):
        return None
    if not isinstance(response := vapp.get("/"), webtest.response.TestResponse):
        return None
    if not isinstance(request := response.request, webtest.app.TestRequest):
        return None
    if not isinstance(environ := request.environ, dict):
        return None
    request = PyramidRequestForTesting(environ)
    request.registry = registry
    request.vapp = vapp
    if isinstance(args, dict):
        params = []
        for key in args:
            if isinstance(value := args[key], (list, tuple)):
                for item in value:
                    params.append((key, item))
            else:
                params.append((key, value))
        request.params = MultiDict(params)
    elif isinstance(args, MultiDict):
        request.params = args
    return request


def portal_custom_search(portal_or_vapp_or_request: Union[PortalFromUtils,
                                                          webtest.app.TestApp, pyramid.request.Request],
                         query: str,
                         method: Optional[str] = None,
                         aggregations: Optional[dict] = None) -> Optional[dict]:
    try:
        from snovault.search.search import search as snovault_search
        from snovault.search.search_utils import make_search_subreq as snovault_make_search_subreq
    except Exception:
        print("ERROR: Cannot execute this code outside of snovault context!", file=sys.stderr, flush=True)
        exit(1)
    if not (isinstance(method, str) and (method := method.strip())):
        method = "GET"
    if not isinstance(request := portal_or_vapp_or_request, pyramid.request.Request):
        if not (request := create_pyramid_request_for_testing(portal_or_vapp_or_request)):
            return None
    if not isinstance(query, str):
        query = "/"
    if not isinstance(aggregations, dict):
        aggregations = None
    request = snovault_make_search_subreq(request, path=query, method=method)
    return snovault_search(None, request, custom_aggregations=aggregations)
