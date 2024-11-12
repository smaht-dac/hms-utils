from prettytable import PrettyTable, HRuleStyle
from hms_utils.argv import ARGV
from hms_utils.chars import chars
from hms_utils.portal.portal_utils import Portal as Portal


def get_consortia_display_value(user: dict) -> str:
    values = []
    if isinstance(consortia := user.get("consortia"), list):
        for consortium in consortia:
            if isinstance(value := consortium.get("identifier"), str):
                values.append(value)
    return ", ".join(values)


def get_submission_centers_display_value(user: dict) -> str:
    values = []
    if isinstance(submission_centers := user.get("submission_centers"), list):
        for submission_center in submission_centers:
            if isinstance(value := submission_center.get("identifier"), str):
                values.append(value)
    return ", ".join(values)


def obsolete_get_group_display_value(user: dict) -> str:
    value = ""
    admin_view = False ; admin_edit = False  # noqa
    if isinstance(user, dict):
        if isinstance(principals_allowed := user.get("principals_allowed"), dict):
            if isinstance(view := principals_allowed.get("view"), list):
                if "group.admin" in view:
                    admin_view = True
            if isinstance(principals_allowed.get("edit"), list):
                if "group.admin" in view:
                    admin_edit = True
    if admin_view:
        if admin_edit:
            value = "admin"
        else:
            value = "admin/view"
    elif admin_edit:
        value = "admin/edit"
    return value


def get_group_display_value(user: dict) -> str:
    values = []
    if isinstance(user, dict):
        if isinstance(groups := user.get("groups"), list):
            values = groups
    return ", ".join(values)


def main():

    argv = ARGV({
        ARGV.REQUIRED(str): ["--env"],
        ARGV.OPTIONAL(str): ["query"],
        ARGV.OPTIONAL(bool): ["--current"],
        ARGV.OPTIONAL(bool): ["--deleted"],
        ARGV.OPTIONAL(bool): ["--inactive"],
        ARGV.OPTIONAL(bool): ["--revoked"],
        ARGV.OPTIONAL(bool): ["--admin"],
        ARGV.OPTIONAL(bool): ["--verbose"],
        ARGV.OPTIONAL(str): ["--submission-center", "--submission-centers", "--centers", "--center", "--sc"]
    })

    portal = Portal.create(argv.env, debug=True)

    if argv.query:
        argv.query = argv.query.lower()
    if argv.current:
        status_query = "status=current"
    elif argv.deleted:
        status_query = "status=deleted&status=revoked"
    elif argv.inactive:
        status_query = "status=inactive"
    elif argv.revoked:
        status_query = "status=revoked"
    else:
        status_query = "status=current&status=inactive&status=deleted&status=revoked"
    if not (users := portal.get(f"/users?{status_query}", limit=10000)):
        return
    if users.status_code == 404:
        return
    users = users.json().get("@graph")

    table = PrettyTable()
    table.field_names = ["N", "USER", "NAME", "CONSORTIA", "CENTERS", "GROUP", "STATUS"]
    table.align = "l"
    table.align["N"] = "r"
    if argv.verbose:
        table.hrules = HRuleStyle.ALL

    users = sorted(users, key=lambda item: item.get("email"))

    ordinal = 1
    for user in users:
        group = get_group_display_value(user)
        if argv.admin and ("admin" not in group):
            if "admin" not in group:
                continue
        submission_centers = get_submission_centers_display_value(user)
        if argv.submission_center:
            if (argv.submission_center.strip().lower() and
                (argv.submission_center.strip().lower() not in ["none", "null"])):  # noqa
                if (argv.submission_center.strip().lower() not in submission_centers.lower()):
                    continue
            if (argv.submission_center.strip().lower() in ["none", "null"]) and submission_centers:
                continue
        user_uuid = user.get("email")
        user_email = user.get("email")
        user_first_name = user.get("first_name")
        user_last_name = user.get("last_name")
        if argv.query:
            if not ((argv.query in user_uuid) or
                    (argv.query in user_email) or
                    (argv.query in user_first_name) or
                    (argv.query in user_last_name)):
                continue
        table.add_row([
            ordinal,
            user_email + ("\n" + user_uuid if argv.verbose else ""),
            user_first_name + " " + user_last_name,
            get_consortia_display_value(user) or chars.null,
            submission_centers or chars.null,
            get_group_display_value(user) or chars.null,
            user.get("status"),
        ])
        ordinal += 1
    if ordinal > 1:
        print(table)


if __name__ == "__main__":
    main()
