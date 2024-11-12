import json
from typing import Tuple
import uuid
from hms_utils.argv import ARGV
from hms_utils.portal.portal_utils import Portal as Portal
from hms_utils.type_utils import is_uuid


def main():

    argv = ARGV({
        ARGV.OPTIONAL(str, "smaht-local"): ["--env"],
        ARGV.OPTIONAL(str): ["--ini"],
        ARGV.AT_LEAST_ONE_OF: ["--env", "--ini"],
        ARGV.OPTIONAL(str): ["--app"],
        ARGV.OPTIONAL(str, "http://localhost:8000"): ["--server"],
        ARGV.OPTIONAL(str, "david_michaels@hms.harvard.edu"): ["--user"],
        ARGV.OPTIONAL(bool): ["--update"],
        ARGV.OPTIONAL(bool): ["--update-database"],
        ARGV.OPTIONAL(bool): ["--update-keys", "--update-keys-file"],
        ARGV.OPTIONAL(bool, True): ["--verbose"],
        ARGV.OPTIONAL(bool): ["--ping"],
        ARGV.OPTIONAL(bool): ["--version"]
    })

    portal = Portal.create(env=argv.env, ini=argv.ini, app=argv.app, verbose=argv.verbose)

    if not (isinstance(user := portal.get_metadata(f"/users/{argv.user}"), dict) and
            is_uuid(user_uuid := user.get("uuid"))):
        print("Cannot find user: {argv.user}")
        exit(0)

    if argv.update:
        argv.update_database = True
        argv.update_keys = True

    access_key_id, access_key_secret, access_key_secret_hash = _generate_access_key_elements()
    access_keys_file_item = _generate_access_keys_file_item(access_key_id, access_key_secret, argv.server)
    access_key_inserts_item = _generate_access_key_inserts_item(access_key_id, access_key_secret_hash, user_uuid)

    print(json.dumps(access_keys_file_item, indent=4))
    print(json.dumps(access_key_inserts_item, indent=4))


def _generate_access_key_inserts_item(access_key_id: str, access_key_secret_hash: str, user_uuid: str) -> dict:
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


if __name__ == "__main__":
    main()
