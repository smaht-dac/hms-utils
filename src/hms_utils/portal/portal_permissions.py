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

    user_principals = get_user_principals(portal_for_user)
    user = portal_for_user.get_metadata("/me")
    user_email = user.get("email")
    user_uuid = user.get("uuid")

    print(f"\n{chars.rarrow} USER: {user_email} {chars.dot} {user_uuid}")
    print_principals(user_principals, uuid_callback=lambda uuid,
                     portal=portal: get_affiliation_identifier(portal, uuid),
                     value_callback=lambda x, y: "foo",
                     header=['abc', 'def', 'ghi'],
                     noheader=False)

    principals_allowed_for_item = get_principals_allowed_for_item(portal, target_item_uuid)
    print('xxx')
    x = [(group, permission) for permission, groups in principals_allowed_for_item.items() for group in groups]
    y = list(set([group for groups in principals_allowed_for_item.values() for group in groups]))

    def find_permissions(data, group_name):
        nonlocal principals_allowed_for_item
        permissions = [permission for permission, groups in data.items() if group_name in groups]
        return f" {chars.dot} ".join(permissions)

    print_principals(y)
    print(json.dumps(x, indent=4))
    print('xxx')
    view_allowed = is_user_allowed_item_access(user_principals, principals_allowed_for_item, Action.VIEW)
    edit_allowed = is_user_allowed_item_access(user_principals, principals_allowed_for_item, Action.EDIT)

    print(f"{chars.rarrow} PORTAL ITEM: {argv.item}")
    print(json.dumps(principals_allowed_for_item, indent=4))

    print(view_allowed)
    print(edit_allowed)

    return status


def get_user_principals(portal_or_key_or_key_name: Union[Portal, dict, str]) -> List[str]:
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
            table.field_names = ["PRINCIPAL/ROLE", "ASSOCIATED UUID", ""]
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


def print_principals_by_action(x):
    pass


def get_affiliation_identifier(portal: Portal, uuid: str) -> Optional[str]:
    if isinstance(portal, Portal) and is_uuid(uuid):
        if isinstance(item := portal.get_metadata(uuid, raise_exception=True), dict):
            return item.get("identifier")
    return None


if __name__ == "__main__":
    sys.exit(main())
