import json
from prettytable import PrettyTable
import sys
from typing import Callable, List, Literal, Optional, Union
from hms_utils.argv import ARGV
from hms_utils.chars import chars
from hms_utils.portal.portal_utils import Portal
from hms_utils.type_utils import is_uuid


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
        ARGV.OPTIONAL([str]): ["--actions", "--action"],
        ARGV.OPTIONAL(bool): ["--ping"],
        ARGV.OPTIONAL(bool): ["--verbose"],
        ARGV.OPTIONAL(bool): ["--debug"],
        ARGV.OPTIONAL(bool): ["--version"]
    })

    status = 0

    if not (portal := Portal.create(argv.env, verbose=argv.verbose, debug=argv.debug, ping=argv.ping)):
        error()

    if argv.user:
        if not (portal_for_user := Portal.create(argv.user or argv.env, verbose=argv.verbose, debug=argv.debug)):
            error()
        if portal.server != portal_for_user.server:
            error(f"Mismatched Portal environments: {portal.server} vs {portal_for_user.server}")
    else:
        portal_for_user = portal

    if not (user := portal_for_user.get_metadata("/me", raise_exception=False)):
        error("Cannot retrieve user info from Portal")

    user_email = user.get("email")
    user_uuid = user.get("uuid")

    user_principals = get_user_principals(portal_for_user)

    print(f"\n{chars.rarrow} USER: {user_email} {chars.dot} {user_uuid}")
    print_principals(user_principals, uuid_callback=lambda uuid, portal=portal: get_affiliation(portal, uuid))
    if argv.debug:
        print(json.dumps(user_principals, indent=4))

    if argv.item:

        if not (principals_allowed_for_item := get_principals_allowed_for_item(portal, argv.item)):
            error(f"Cannot access Portal item: {argv.item}")

        if principals_allowed_for_item:

            print(f"\n{chars.rarrow} PORTAL ITEM: {argv.item}")
            print_principals_with_actions(principals_allowed_for_item)
            if argv.debug:
                print(json.dumps(principals_allowed_for_item, indent=4))

            if (actions := argv.actions) or (actions := sorted(list(principals_allowed_for_item.keys()))):
                print(f"\n{chars.rarrow} PERMISSIONS: {argv.item} {chars.larrow_hollow} {user_email}")
                for action in actions:
                    action_allowed = is_user_allowed_item_access(user_principals, principals_allowed_for_item, action)
                    print(f"  {chars.dot} ACTION: {action} {chars.rarrow_hollow}"
                          f" {f'ALLOWED' if action_allowed else 'FORBIDDEN'}")
                    if not action_allowed:
                        status = 1
    print()

    return status


def get_user_principals(portal_or_key_or_key_name: Union[Portal, dict, str]) -> List[str]:
    """
    Returns the principals for the given user, specified be either a Portal object,
    or a key name (i.e. e.g. in the ~/.smaht-keys.json file), or a key (i.e. e.g. a
    dictionary like {"key": "REDACTED", "secret", server: "http://data.smaht.org"}).
    The result looks something like this:
        [
            "system.Everyone",
            "system.Authenticated",
            "role.submission_center_member_rw.9626d82e-8110-4213-ac75-0a50adf890ff",
            "accesskey.3HJDFQAD",
            "submits_for.9626d82e-8110-4213-ac75-0a50adf890ff",
            "role.consortium_member_rw",
            "group.submitter",
            "role.consortium_member_create",
            "userid.74fef71a-dfc1-4aa4-acc0-cedcb7ac1d68",
            "role.consortium_member_rw.358aed10-9b9d-4e26-ab84-4bd162da182b"
        ]
    Note that this uses the (circa 2024-11-14) debugging/troubleshooting endpoint /debug_user_principals.
    """
    if isinstance(portal_or_key_or_key_name, Portal):
        portal_for_user = portal_or_key_or_key_name
    elif isinstance(portal_or_key_or_key_name, (dict, str)):
        portal_for_user = Portal(portal_or_key_or_key_name)
    else:
        return []
    if not (user_principals := portal_for_user.get_metadata("/debug_user_principals")):
        return []
    return user_principals


def get_principals_allowed_for_item(portal: Portal, query: str,
                                    action: Optional[ActionType] = None) -> Union[dict, List[str]]:
    """
    Returns the principals allowed fro the given Portal item (query). If an action (e.g. view or edit)
    is NOT given then the esult looks something like this:
        {
            "view": [
                "group.admin",
                "group.read-only-admin",
                "remoteuser.INDEXER",
                "role.submission_center_member_rw",
                "role.submission_center_member_rw.9626d82e-8110-4213-ac75-0a50adf890ff"
            ],
            "edit": [
                "group.admin",
                "group.submitter"
            ]
        }
    If an action IS given (e.g. view or edit) then the result looks something like this:
        [
            "group.admin",
            "group.read-only-admin",
            "remoteuser.INDEXER",
            "role.submission_center_member_rw",
            "role.submission_center_member_rw.9626d82e-8110-4213-ac75-0a50adf890ff"
        ]
    """
    if action not in ActionType:
        action = None
    if not (isinstance(portal, Portal) and isinstance(query, str) and query):
        return [] if action else {}
    if not isinstance(item := portal.get_metadata(query, raise_exception=False), dict):
        return [] if action else {}
    if not isinstance(principals_allowed_for_item := item.get("principals_allowed"), dict):
        return [] if action else {}
    if action:
        if not isinstance(principals_allowed_for_item_for_action := principals_allowed_for_item.get(action), list):
            return []
        return principals_allowed_for_item_for_action
    else:
        return principals_allowed_for_item


def is_user_allowed_item_access(user_principals_or_portal_or_key_or_key_name: Union[List[str], Portal, dict, str],
                                principals_allowed_for_item: dict, action: str) -> bool:
    if isinstance(user_principals_or_portal_or_key_or_key_name, (Portal, dict, str)):
        user_principals = get_user_principals(user_principals_or_portal_or_key_or_key_name)
    elif isinstance(user_principals_or_portal_or_key_or_key_name, list):
        user_principals = user_principals_or_portal_or_key_or_key_name
    else:
        return False
    if not isinstance(user_principals, list):
        return False
    if not isinstance(principals_allowed_for_item, dict):
        return False
    if not (isinstance(action, str) and (action := action.strip())):
        return False
    if not isinstance(principals_allowed_for_item_for_action := principals_allowed_for_item.get(action), list):
        return False
    for principal_allowed_for_item_for_action in principals_allowed_for_item_for_action:
        if principal_allowed_for_item_for_action in user_principals:
            return True
    return False


def print_principals(principals: List[str], message: Optional[str] = None,
                     value_callback: Optional[Callable] = None,
                     value_header: Optional[str] = None,
                     uuid_callback: Optional[Callable] = None,
                     parse_userid: bool = False,
                     header: Optional[List[str]] = None,
                     noheader: bool = False,
                     return_value: bool = False,
                     nosort: bool = False):

    def uuid_specific_principal(principal):  # noqa
        principal_uuid = ""
        if principal.startswith("role."):
            principal = principal.replace("role.", "role/")
        if (index := principal.find(".")) > 0:
            if is_uuid(value := principal[index + 1:]):
                principal_uuid = value
                principal = principal[0:index]
        if principal.startswith("role/"):
            principal = principal.replace("role/", "role.")
        return principal, principal_uuid

    header = header if isinstance(header, list) and (noheader is not True) else None
    rows = []
    for principal in principals:
        principal, principal_uuid = uuid_specific_principal(principal)
        if callable(uuid_callback):
            if principal_uuid_annotation := uuid_callback(principal_uuid):
                principal_uuid += f" {chars.dot} {principal_uuid_annotation}"
        if principal_uuid:
            rows.append([principal, principal_uuid])
            if value_callback:
                rows[len(rows) - 1].append("")
        else:
            rows.append([principal, ""])
            if value_callback:
                rows[len(rows) - 1].append("")

    table = PrettyTable()
    if header:
        table.field_names = header
    elif noheader is not True:
        if callable(value_callback):
            table.field_names = ["PRINCIPAL/ROLE", "ASSOCIATED UUID",
                                 value_header if isinstance(value_header, str) else ""]
        else:
            table.field_names = ["PRINCIPAL/ROLE", "ASSOCIATED UUID"]
    else:
        table.header = False
    for row in rows:
        if value_callback and (role := value_callback(row[0], row[1])):
            row[2] = role
    if nosort is not True:
        rows.sort(key=lambda row: f"{row[0]}_{row[1]}")
    for row in rows:
        table.add_row([item or chars.null for item in row])
    table.align = "l"
    output = f"{message}\n" if message else ""
    output += str(table)
    if return_value:
        return output
    print(output)


def print_principals_with_actions(principals_allowed_for_item_by_action: dict) -> None:
    def find_actions(principal, principal_uuid) -> Optional[str]:
        nonlocal principals_allowed_for_item_by_action
        if isinstance(principal, str):
            if is_uuid(principal_uuid):
                principal += f".{principal_uuid}"
            actions = [action for action, items in principals_allowed_for_item_by_action.items() if principal in items]
            return f" {chars.dot} ".join(actions)
    principals_allowed_for_item = [item for items in principals_allowed_for_item_by_action.values() for item in items]
    principals_allowed_for_item = list(set(principals_allowed_for_item))
    print_principals(principals_allowed_for_item, value_callback=find_actions, value_header="ACTION      ")


def get_affiliation(portal: Portal, uuid: str) -> Optional[str]:
    if isinstance(portal, Portal) and is_uuid(uuid):
        if isinstance(item := portal.get_metadata(uuid, raise_exception=True), dict):
            return item.get("identifier")
    return None


def error(message: Optional[str] = None, exit: bool = True, status: int = 1) -> None:
    if isinstance(message, str) and message:
        print(f"ERROR: {str(message)}", file=sys.stderr)
    if exit is not False:
        sys.exit(status if isinstance(status, int) else 1)


if __name__ == "__main__":
    sys.exit(main())
