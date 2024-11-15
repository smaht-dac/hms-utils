import json
from functools import lru_cache
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
    EXPAND = "expand"
    INDEX = "index"
    LIST = "list"
    RESTRICTED_FIELDS = "restricted_fields"
    SEARCH = "search"
    VIEW = "view"
    VIEW_DETAILS = "view_details"
    VIEW_RAW = "view_raw"
    VISIBLE_FOR_EDIT = "visible_for_edit"


ActionType = Literal[
    Action.ADD,
    Action.EDIT,
    Action.CREATE,
    Action.EXPAND,
    Action.INDEX,
    Action.LIST,
    Action.RESTRICTED_FIELDS,
    Action.SEARCH,
    Action.VIEW,
    Action.VIEW_DETAILS,
    Action.VIEW_RAW,
    Action.VISIBLE_FOR_EDIT
]


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

    if argv.item:
        if not (principals_allowed_for_item := get_principals_allowed_for_item(portal, argv.item)):
            error(f"Cannot access Portal item: {argv.item}")
    else:
        principals_allowed_for_item = None

    print(f"\n{chars.rarrow} USER: {user_email} {chars.dot} {user_uuid}")
    print_user_principals(user_principals, principals_allowed_for_item, portal)
    if argv.debug:
        print(json.dumps(user_principals, indent=4))

    if principals_allowed_for_item:

        item_type = get_portal_item_type(portal, argv.item)
        print(f"\n{chars.rarrow} PORTAL ITEM: {argv.item}{f' {chars.dot} {item_type}' if item_type else ''}")
        print_principals_with_actions(principals_allowed_for_item, user_principals)
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
    is NOT given then the result looks something like this:
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
    # if not isinstance(item := portal.get_metadata(query, raise_exception=False), dict):
    if not isinstance(item := get_portal_item(portal, query), dict):
        return [] if action else {}
    if not isinstance(principals_allowed_for_item := item.get("principals_allowed"), dict):
        return [] if action else {}
    if action:
        if not isinstance(principals_allowed_for_item_for_action := principals_allowed_for_item.get(action), list):
            return []
        return principals_allowed_for_item_for_action
    else:
        return principals_allowed_for_item


@lru_cache(maxsize=1)
def get_portal_item(portal: Portal, query: str) -> Optional[dict]:
    return portal.get_metadata(query, raise_exception=False)


def get_portal_item_type(portal: Portal, query: str) -> Optional[dict]:
    if item := get_portal_item(portal, query):
        return Portal.get_item_type(item)
    return None


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
                     principal_callback: Optional[Callable] = None,
                     principal_uuid_callback: Optional[Callable] = None,
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
        if callable(principal_callback):
            if principal_annotation := principal_callback(principal, principal_uuid):
                principal += principal_annotation
        if callable(principal_uuid_callback):
            if principal_uuid_annotation := principal_uuid_callback(principal_uuid):
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


def print_user_principals(user_principals: List[str],
                          principals_allowed_for_item: Optional[dict] = None,
                          portal: Optional[Portal] = None) -> None:
    if isinstance(principals_allowed_for_item, dict):
        principals_allowed_for_item_flattened = [item for items in principals_allowed_for_item.values()
                                                 for item in items]
        principals_allowed_for_item_flattened = list(set(principals_allowed_for_item_flattened))
    else:
        principals_allowed_for_item_flattened = None
    def principal_annotation(principal: str, principal_uuid: Optional[str] = None):  # noqa
        nonlocal principals_allowed_for_item_flattened
        if isinstance(principal, str) and principal:
            if isinstance(principal_uuid, str) and principal_uuid:
                principal += f"{principal_uuid}"
            if principal in principals_allowed_for_item_flattened:
                return f" {chars.larrow}{chars.larrow}{chars.larrow}"
    def principal_uuid_annotation(principal_uuid: str) -> Optional[str]:  # noqa
        nonlocal portal
        return get_affiliation(portal, principal_uuid)
    print_principals(user_principals,
                     principal_callback=principal_annotation if principals_allowed_for_item_flattened else None,
                     principal_uuid_callback=principal_uuid_annotation if isinstance(portal, Portal) else None)


def print_principals_with_actions(principals_allowed_for_item_by_action: dict,
                                  user_principals: Optional[List[str]] = None) -> None:
    def find_actions(principal, principal_uuid) -> Optional[str]:
        nonlocal principals_allowed_for_item_by_action
        if isinstance(principal, str):
            if is_uuid(principal_uuid):
                principal += f".{principal_uuid}"
            actions = [action for action, items in principals_allowed_for_item_by_action.items() if principal in items]
            return f" {chars.dot} ".join(actions)
    def principal_annotation(principal: str, principal_uuid: Optional[str] = None) -> None:  # noqa
        nonlocal user_principals
        if isinstance(principal, str) and principal:
            if isinstance(principal_uuid, str) and principal_uuid:
                principal += f"{principal_uuid}"
            if principal in user_principals:
                return f" {chars.larrow}{chars.larrow}{chars.larrow}"
    principals_allowed_for_item = [item for items in principals_allowed_for_item_by_action.values() for item in items]
    principals_allowed_for_item = list(set(principals_allowed_for_item))
    print_principals(principals_allowed_for_item,
                     principal_callback=principal_annotation if isinstance(user_principals, list) else None,
                     value_callback=find_actions, value_header="ACTION     ")


def print_acls(acls: List[tuple], message: Optional[str] = None, nosort: bool = False):
    rows = []
    for acl_item in acls:
        ace_action, ace_principal, ace_permissions = acl_item
        rows.append([ace_principal,
                     (f"{ace_action} {chars.dot}"
                      f" {'/'.join(ace_permissions) if isinstance(ace_permissions, list) else str(ace_permissions)}")])
    table = PrettyTable()
    table.header = False
    if nosort is not True:
        rows.sort(key=lambda row: row[0])
    for row in rows:
        table.add_row(row)
    table.align = "l"
    if message:
        print(message)
    print(table)


def print_acls_and_principals(acls: List[tuple], principals: List[str],
                              message: Optional[str] = None, permission: Optional[str] = None):
    def find_matching_acl():  # noqa
        # FYI: See pyramid/authorization.py ...
        nonlocal acls, principals, permission
        for acl_item in acls:
            acl_action, acl_principal, acl_permissions = acl_item
            if acl_principal in principals:
                if permission in acl_permissions:
                    return acl_item
        return None
    matching_acl = find_matching_acl()
    def acl_value(principal, uuid):  # noqa
        nonlocal acls, principals, permission
        if uuid:
            principal = f"{principal}.{uuid}"
        for acl_item in acls:
            acl_action, acl_principal, acl_permissions = acl_item
            if acl_principal == principal:
                value = (f"{acl_action} {chars.dot}"
                         f" {'/'.join(acl_permissions) if isinstance(acl_permissions, list) else str(acl_permissions)}")
                if acl_item == matching_acl:
                    value += f" {chars.larrow}{chars.larrow}{chars.larrow}"
                elif permission in acl_permissions:
                    value += f" {chars.larrow_hollow}"
                return value
        return ""
    output = print_principals(principals, value_callback=acl_value, value_header="PERMISSION", return_value=True)
    acls_not_in_principals = []
    for acl_item in acls:
        if acl_item[1] not in principals:
            acls_not_in_principals.append(acl_item)
    if acls_not_in_principals:
        if (index := output.rfind("\n")) > 0:
            separator = output[index + 1:].replace("+", "-")
            separator = "+" + ((len(separator) - 2) * "-") + "+"
        output += "\n| ACLs NOT IN PRINCIPALS ...\n" + separator
        for acl_item in acls_not_in_principals:
            acl_item_output = (f"| {acl_item[1]} {chars.dot} {acl_item[0]} {chars.dot}"
                               f" {'/'.join(acl_item[2]) if isinstance(acl_item[2], list) else str(acl_item[2])}")
            output += f"\n{acl_item_output}"
            output += ((len(separator) - len(acl_item_output) - 1) * " ") + "|"
        output += "\n" + separator
    if message:
        print(message)
    print(output)


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
