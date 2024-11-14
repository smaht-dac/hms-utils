from prettytable import PrettyTable
from typing import Callable, List, Optional
from hms_utils.chars import chars
from hms_utils.type_utils import is_uuid


def print_principals(principals: List[str], message: Optional[str] = None,
                     value_callback: Optional[Callable] = None,
                     value_header: Optional[str] = None,
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

    rows = [] ; header = None  # noqa
    for principal in principals:
        principal, principal_uuid = uuid_specific_principal(principal)
        if principal_uuid:
            if (principal == "userid") and (not header):
                header = [principal_uuid, "ROLE UUID"]
                if value_callback:
                    header.append(value_header or "")
            else:
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
        if value_callback and (role := value_callback("userid", header[0])):
            rows.append(["userid", header[0], role])
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


def print_roles(roles: dict, message: Optional[str] = None, nosort: bool = False):
    def role_value(principal, uuid):
        nonlocal roles
        return roles.get(f"{principal}.{uuid}") if uuid else roles.get(principal)
    print_principals(list(roles.keys()), message=message,
                     value_callback=role_value, value_header="ROLE VALUE", nosort=nosort)


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


if False:

    import json
    principals = ['group.submitter', 'role.consortium_member_create', 'accesskey.7JFE33AN', 'role.submission_center_member_rw.9626d82e-8110-4213-ac75-0a50adf890ff', 'system.Authenticated', 'group.admin', 'submits_for.9626d82e-8110-4213-ac75-0a50adf890ff', 'system.Everyone', 'role.consortium_member_rw', 'userid.74fef71a-dfc1-4aa4-acc0-cedcb7ac1d68', 'role.consortium_member_rw.358aed10-9b9d-4e26-ab84-4bd162da182b']  # noqa
    print(json.dumps(principals, indent=4))
    print_principals(principals)


if False:

    acls = [('Allow', 'group.submitter', ['edit']), ('Allow', 'role.submission_center_member_rw', ['view']), ('Allow', 'group.admin', ['view', 'edit']), ('Allow', 'group.read-only-admin', ['view']), ('Allow', 'remoteuser.INDEXER', ['view']), ('Allow', 'remoteuser.EMBED', ['view']), ('Deny', 'system.Everyone', ['view', 'edit'])]  # noqa

    principals = {'submits_for.9626d82e-8110-4213-ac75-0a50adf890ff', 'system.Everyone', 'group.admin', 'accesskey.7JFE33AN', 'role.owner', 'role.submission_center_member_create', 'userid.74fef71a-dfc1-4aa4-acc0-cedcb7ac1d68', 'role.submission_center_member_rw', 'group.submitter', 'role.consortium_member_rw.358aed10-9b9d-4e26-ab84-4bd162da182b', 'role.consortium_member_create', 'role.consortium_member_rw', 'system.Authenticated', 'role.submission_center_member_rw.9626d82e-8110-4213-ac75-0a50adf890ff'}  # noqa

    print_acls(acls)
    print_principals(principals)
    print_acls_and_principals(acls, principals, permission="view")


if False:
    acl = [('Allow', 'group.submitter', ['edit']), ('Allow', 'role.submission_center_member_rw', ['view']), ('Allow', 'group.admin', ['view', 'edit']), ('Allow', 'group.read-only-admin', ['view']), ('Allow', 'remoteuser.INDEXER', ['view']), ('Allow', 'remoteuser.EMBED', ['view']), ('Deny', 'system.Everyone', ['view', 'edit'])]  # noqa
    principals = {'accesskey.JMGZMR42', 'role.consortium_member_rw.358aed10-9b9d-4e26-ab84-4bd162da182b', 'role.submission_center_member_rw.055cfde3-f82c-4d32-851d-b8061c7e2b95', 'system.Everyone', 'role.consortium_member_create', 'role.consortium_member_rw', 'submits_for.9626d82e-8110-4213-ac75-0a50adf890ff', 'system.Authenticated', 'role.submission_center_member_create', 'group.submitter', 'userid.0d565156-00db-4948-82fe-021d151a5daf'}  # noqa
    print_acls_and_principals(acl, principals)

if False:

    acls = [('Allow', 'group.admin', ['view', 'edit']), ('Allow', 'group.read-only-admin', ['view']), ('Allow', 'remoteuser.INDEXER', ['view']), ('Allow', 'remoteuser.EMBED', ['view']), ('Deny', 'system.Everyone', ['view', 'edit'])]  # noqa
    print_acls(acls)
    principals = ['system.Everyone', 'group.admin', 'role.consortium_member_rw.358aed10-9b9d-4e26-ab84-4bd162da182b', 'role.consortium_member_rw', 'system.Authenticated', 'userid.74fef71a-dfc1-4aa4-acc0-cedcb7ac1d68', 'submits_for.9626d82e-8110-4213-ac75-0a50adf890ff', 'role.consortium_member_create', 'accesskey.Z4WJPLBI', 'group.submitter', 'role.submission_center_member_rw.9626d82e-8110-4213-ac75-0a50adf890ff']  # noqa
    print_principals(principals)

    print_acls_and_principals(acls, principals, permission="view")

    roles = {'role.submission_center_member_rw.9626d82e-8110-4213-ac75-0a50adf890ff': 'role.submission_center_member_rw', 'submits_for.9626d82e-8110-4213-ac75-0a50adf890ff': 'role.submission_center_member_create', 'role.consortium_member_rw.358aed10-9b9d-4e26-ab84-4bd162da182b': 'role.consortium_member_rw', 'userid.74fef71a-dfc1-4aa4-acc0-cedcb7ac1d68': 'role.owner'}  # noqa
    print_roles(roles)
