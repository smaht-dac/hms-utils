import json
import sys
from typing import List, Literal, Optional, Union
from hms_utils.argv import ARGV
from hms_utils.portal.portal_utils import Portal


class Action:
    ADD = "add"
    EDIT = "edit"
    CREATE = "create"
    VIEW = "view"
    VIEW_DETAILS = "view_details"
    VISIBLE_FOR_EDIT = "visible_for_edit"


ActionType = Literal[Action.ADD, Action.EDIT, Action.CREATE,
                     Action.VIEW, Action.VIEW_DETAILS, Action.VISIBLE_FOR_EDIT]


def main():

    argv = ARGV({
        ARGV.OPTIONAL(str): ["item"],
        ARGV.OPTIONAL(str): ["--env"],
        ARGV.OPTIONAL(str): ["--user"],
        ARGV.OPTIONAL(bool): ["--ping"],
        ARGV.OPTIONAL(bool): ["--verbose"],
        ARGV.OPTIONAL(bool): ["--version"]
    })

    status = 0

    target_item_uuid = argv.item

    portal = Portal.create(argv.env, verbose=argv.verbose, ping=argv.ping)

    if argv.user:
        portal_for_user = Portal.create(argv.user or argv.env)
        if portal.server != portal_for_user.server:
            print(f"Mismatched Portal environments: {portal.server} vs {portal_for_user.server}")
            exit(1)
    else:
        portal_for_user = portal

    principals_for_user = get_principals_for_user(portal_for_user)
    principals_allowed_for_item = get_principals_allowed_for_item(portal, target_item_uuid)
    view_allowed = is_user_allowed_item_access(principals_for_user, principals_allowed_for_item, Action.VIEW)
    edit_allowed = is_user_allowed_item_access(principals_for_user, principals_allowed_for_item, Action.EDIT)

    print(f"PRINCIPALS FOR USER: {argv.user}")
    print(json.dumps(principals_for_user, indent=4))

    print(f"PRINCIPALS FOR ITEM: {argv.item}")
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
                                    action: Optional[ActionType] = None) -> Optional[Union[dict, List[str]]]:
    # if not (isinstance(action, str) and (action := action.strip())):
    if action not in ActionType:
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
