import json
import sys
from typing import List, Optional, Union
from hms_utils.portal.portal_utils import Portal


def main():

    status = 0

    env = "smaht-local"
    user_env = "smaht-local-feng"
    target_item_uuid = "670cbe0e-e8b4-4dae-b9ed-8bf33bd91ad5"

    portal = Portal(env)
    portal_for_user = Portal(user_env)

    principals_for_user = get_principals_for_user(portal_for_user)
    principals_allowed_for_item = get_principals_allowed_for_item(portal, target_item_uuid)
    view_allowed = is_user_allowed_item_access(principals_for_user, principals_allowed_for_item, "view")
    edit_allowed = is_user_allowed_item_access(principals_for_user, principals_allowed_for_item, "edit")

    print(json.dumps(principals_for_user, indent=4))
    print(json.dumps(principals_allowed_for_item, indent=4))

    print(view_allowed)
    print(edit_allowed)

    return status


def get_principals_for_user(portal_or_key_or_key_name: Union[Portal, dict, str]) -> List[str]:
    if isinstance(portal_or_key_or_key_name, Portal):
        portal_for_user = portal_or_key_or_key_name
    elif isinstance(portal_or_key_or_key_name, (dict, str)):
        portal_for_user = Portal(portal_or_key_or_key_name)
    else:
        return []
    if not (principals_for_user := portal_for_user.get_metadata("/debug_user_principals")):
        return []
    return principals_for_user


def get_principals_allowed_for_item(portal: Portal, query: str,
                                    action: Optional[str] = None) -> Optional[Union[dict, List[str]]]:
    if not (isinstance(action, str) and (action := action.strip())):
        action = None
    if not (isinstance(portal, Portal) and isinstance(query, str) and query):
        return [] if action else {}
    if not isinstance(item := portal.get_metadata(query), dict):
        return [] if action else {}
    if not isinstance(principals_allowed_for_item := item.get("principals_allowed"), dict):
        return [] if action else {}
    if action:
        if not isinstance(principals_allowed_for_item_for_action := principals_allowed_for_item.get(action), list):
            return []
        return principals_allowed_for_item_for_action
    else:
        return principals_allowed_for_item


def is_user_allowed_item_access(principals_for_user_or_portal_or_key_or_key_name: Union[List[str], Portal, dict, str],
                                principals_allowed_for_item: dict, action: str) -> bool:
    if isinstance(principals_for_user_or_portal_or_key_or_key_name, (Portal, dict, str)):
        principals_for_user = get_principals_for_user(principals_for_user_or_portal_or_key_or_key_name)
    elif isinstance(principals_for_user_or_portal_or_key_or_key_name, list):
        principals_for_user = principals_for_user_or_portal_or_key_or_key_name
    else:
        return False
    if not isinstance(principals_for_user, list):
        return False
    if not isinstance(principals_allowed_for_item, dict):
        return False
    if not (isinstance(action, str) and (action := action.strip())):
        return False
    if not isinstance(principals_allowed_for_item_for_action := principals_allowed_for_item.get(action), list):
        return False
    for principal_allowed_for_item_for_action in principals_allowed_for_item_for_action:
        if principal_allowed_for_item_for_action in principals_for_user:
            return True
    return False


if __name__ == "__main__":
    sys.exit(main())
