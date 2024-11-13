import io
import json
import os
import sys
from typing import Tuple
import uuid
from dcicutils.command_utils import yes_or_no
from hms_utils.argv import ARGV
from hms_utils.chars import chars
from hms_utils.portal.portal_utils import Portal as Portal
from hms_utils.type_utils import is_uuid

_ACCESS_KEY_TYPE_NAME = "AccessKey"
_DEFAULT_APP = "smaht"
_DEFAULT_SERVER = "http://localhost:8000"


def main():

    argv = ARGV({
        ARGV.OPTIONAL(str): ["--env"],
        ARGV.OPTIONAL(str): ["--ini"],
        ARGV.OPTIONAL(str): ["--app"],
        ARGV.REQUIRED(str): ["--user"],
        ARGV.OPTIONAL(str): ["--access-keys-file-property-name", "--name"],
        ARGV.OPTIONAL(bool): ["--update"],
        ARGV.OPTIONAL(bool): ["--update-database"],
        ARGV.OPTIONAL(bool): ["--update-keys", "--update-keys-file"],
        ARGV.OPTIONAL(str): ["--server"],
        ARGV.OPTIONAL(bool): ["--quiet"],
        ARGV.OPTIONAL(bool): ["--verbose"],
        ARGV.OPTIONAL(bool): ["--debug"],
        ARGV.OPTIONAL(bool): ["--yes", "--force"],
        ARGV.OPTIONAL(bool): ["--ping"],
        ARGV.OPTIONAL(bool): ["--version"]
    })

    portal = Portal.create(argv.ini or argv.env, app=argv.app, verbose=argv.verbose, debug=argv.debug, ping=argv.ping)

    if not (isinstance(user := portal.get_metadata(f"/users/{argv.user}", raise_exception=False), dict) and
            is_uuid(user_uuid := user.get("uuid"))):
        print(f"Cannot find user: {argv.user}")
        exit(0)

    access_keys_file = portal.keys_file
    access_keys_file_property_name = argv.access_keys_file_property_name or portal.env
    access_keys_server = portal.server or argv.server or _DEFAULT_SERVER
    access_keys_app = portal.app or argv.app or _DEFAULT_APP

    if not access_keys_file:
        access_keys_file = os.path.expanduser(f"~/.{access_keys_app}-keys.json")
    if not access_keys_file_property_name:
        access_keys_file_property_name = f"{access_keys_app}-local"

    access_key_id, access_key_secret, access_key_secret_hash = _generate_access_key_elements()
    access_keys_file_item = _generate_access_keys_file_item(access_key_id, access_key_secret, access_keys_server)
    access_key_portal_inserts_item = _generate_access_key_portal_inserts_item(access_key_id,
                                                                              access_key_secret_hash, user_uuid)
    if not argv.quiet:
        print(f"Newly generated portal access-key record suitable for: {access_keys_file} ...")
        print(json.dumps(access_keys_file_item, indent=4))
        print(f"Newly generated portal access-key record suitable for insert ...")
        print(json.dumps(access_key_portal_inserts_item, indent=4))

    if argv.update:
        argv.update_database = True
        argv.update_keys = True

    if argv.update_database:
        if (not argv.quiet) or argv.verbose:
            print(f"Updating portal database with newly generated access-key item:"
                  f" {access_keys_server} {chars.dot} {access_key_id}")
        _update_portal_with_access_key(portal, access_key_portal_inserts_item)

    if argv.update_keys:
        if (not argv.quiet) or argv.verbose:
            print(f"Updating access-keys file with newly generated access-key item:"
                  f" {access_keys_file} {chars.dot} {access_keys_file_property_name}")
        if os.path.exists(access_keys_file):
            try:
                with io.open(access_keys_file, "r") as f:
                    access_keys_file_json = json.load(f)
            except Exception:
                print(f"Cannot read existing access-keys file: {access_keys_file}")
                exit(1)
            if access_keys_file_json.get(access_keys_file_property_name):
                if not argv.yes:
                    print(f"Item already exists for access-key item ({access_keys_file_property_name})"
                          f" in access-keys file: {access_keys_file}")
                    if not yes_or_no(f"Overwrite access-key item {access_keys_file_property_name}?"):
                        return 1
                elif argv.verbose:
                    print(f"Overwriting existing item for access-key ({access_keys_file_property_name})"
                          f" in access-keys file: {access_keys_file}")
            access_keys_file_json[access_keys_file_property_name] = access_keys_file_item
        else:
            access_keys_file_json = access_keys_file_item
        try:
            with io.open(access_keys_file, "w") as f:
                json.dump(access_keys_file_json, fp=f, indent=4)
        except Exception:
            print(f"Cannot write access-keys file: {access_keys_file}")
            exit(1)


def _generate_access_key_portal_inserts_item(access_key_id: str, access_key_secret_hash: str, user_uuid: str) -> dict:
    return {
        "status": "current",
        "user": user_uuid,
        "description": f"Manually generated local access-key for testing.",
        "access_key_id": access_key_id,
        "secret_access_key_hash": access_key_secret_hash,
        "uuid": str(uuid.uuid4())
    }


def _generate_access_keys_file_item(access_key_id: str, access_key_secret: str, server: str) -> dict:
    return {
        "key": access_key_id,
        "secret": access_key_secret,
        "server": server
    }


def _generate_access_key_elements() -> Tuple[str, str, str]:
    from passlib.context import CryptContext
    from passlib.registry import register_crypt_handler
    try:
        from snovault.authentication import (
            generate_password as snovault_generate_access_key_secret,
            generate_user as snovault_generate_access_key
        )
        from snovault.edw_hash import EDWHash as snovault_edwhash
    except Exception:
        print("Cannot import dcicsnovault modules which are needed for access-key secret generation.")
        exit(1)
    # Generate access-key and secret like snovault does.
    access_key = snovault_generate_access_key()
    access_key_secret = snovault_generate_access_key_secret()
    # Generate access-key secret hash like snovault does. See: snovault/authentication.py
    passlib_properties = {"schemes": "edw_hash, unix_disabled"}
    register_crypt_handler(snovault_edwhash)
    access_key_hash_secret = CryptContext(**passlib_properties).hash(access_key_secret)
    # Return the access-key and its associated secret and secret hash (for the portal database item) values.
    return access_key, access_key_secret, access_key_hash_secret


def _update_portal_with_access_key(portal: Portal, data: dict) -> bool:
    if portal.ini_file:
        return _load_data(portal, data)
    else:
        return portal.post_metadata(_ACCESS_KEY_TYPE_NAME, data)
    pass


def _load_data(portal: Portal, data: dict, data_type: str = _ACCESS_KEY_TYPE_NAME) -> bool:
    try:
        from snovault.loadxl import load_all as snovault_load_all
    except Exception:
        print("Cannot import dcicsnovault modules which are needed for local access-key loading.")
        exit(1)
    if isinstance(data, dict):
        data = [data]
    elif not isinstance(data, list):
        return False
    if not isinstance(data_type, str):
        return False
    data = {data_type: data}
    snovault_load_all(portal.vapp, inserts=data, docsdir=None, overwrite=True, itype=[data_type], from_json=True)
    return True


if __name__ == "__main__":
    sys.exit(main())
