from prettytable import PrettyTable, HRuleStyle
from hms_utils.argv import ARGV
from hms_utils.chars import chars
from hms_utils.portal.portal_utils import Portal as Portal


def main():

    argv = ARGV({
        ARGV.OPTIONAL(str): ["--env"],
        ARGV.OPTIONAL(str): ["query"],
        ARGV.OPTIONAL(bool): ["--current"],
        ARGV.OPTIONAL(bool): ["--deleted"],
        ARGV.OPTIONAL(bool): ["--inactive"],
        ARGV.OPTIONAL(bool): ["--revoked"],
        ARGV.OPTIONAL(bool): ["--admin"],
        ARGV.OPTIONAL(bool): ["--database"],
        ARGV.OPTIONAL(bool): ["--verbose"],
        ARGV.OPTIONAL(bool): ["--debug"],
        ARGV.OPTIONAL(bool): ["--ping"],
        ARGV.OPTIONAL(str): ["--submission-center", "--submission-centers", "--centers", "--center", "--sc"]
    })

    portal = Portal.create(argv.env, verbose=argv.verbose, debug=argv.debug, ping=argv.ping)

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
    if not (users := portal.get_metadata(f"/users?{status_query}", limit=10000, database=argv.database)):
        return
    users = users.get("@graph")

    table = PrettyTable()
    table.field_names = ["N", "USER", "NAME", "CONSORTIA", "CENTERS", "GROUP", "STATUS"]
    table.align = "l"
    table.align["N"] = "r"
    if argv.verbose:
        table.hrules = HRuleStyle.ALL

    users = sorted(users, key=lambda item: item.get("email"))

    ordinal = 1
    for user in users:
        group = _get_group_display_value(user)
        if argv.admin and ("admin" not in group):
            if "admin" not in group:
                continue
        submission_centers = _get_submission_centers_display_value(user, verbose=argv.verbose)
        if argv.submission_center:
            if (argv.submission_center.strip().lower() and
                (argv.submission_center.strip().lower() not in ["none", "null"])):  # noqa
                if (argv.submission_center.strip().lower() not in submission_centers.lower()):
                    continue
            if (argv.submission_center.strip().lower() in ["none", "null"]) and submission_centers:
                continue
        user_uuid = user.get("uuid", "")
        user_email = user.get("email", "")
        user_first_name = user.get("first_name", "")
        user_last_name = user.get("last_name", "")
        if argv.query:
            if not ((argv.query in user_uuid.lower()) or
                    (argv.query in user_email.lower()) or
                    (argv.query in user_first_name.lower()) or
                    (argv.query in user_last_name.lower())):
                continue
        table.add_row([
            ordinal,
            user_email + ("\n" + user_uuid if argv.verbose else ""),
            user_first_name + " " + user_last_name,
            _get_consortia_display_value(user, verbose=argv.verbose) or chars.null,
            submission_centers or chars.null,
            _get_group_display_value(user) or chars.null,
            user.get("status"),
        ])
        ordinal += 1
    if ordinal > 1:
        print(table)


def _get_consortia_display_value(user: dict, verbose: bool = False) -> str:
    values = [] ; values_verbose = ""  # noqa
    if isinstance(consortia := user.get("consortia"), list):
        for consortium in consortia:
            if isinstance(value := consortium.get("identifier"), str):
                values.append(value)
                if (verbose is True) and (value_uuid := consortium.get("uuid")):
                    values_verbose += "\n" + value_uuid
    values = ", ".join(values)
    if values_verbose:
        values += values_verbose
    return values


def _get_submission_centers_display_value(user: dict, verbose: bool = False) -> str:
    values = [] ; values_verbose = ""  # noqa
    if isinstance(submission_centers := user.get("submission_centers"), list):
        for submission_center in submission_centers:
            if isinstance(value := submission_center.get("identifier"), str):
                values.append(value)
                if (verbose is True) and (value_uuid := submission_center.get("uuid")):
                    values_verbose += "\n" + value_uuid
    values = ", ".join(values)
    if values_verbose:
        values += values_verbose
    return values


def _get_group_display_value(user: dict) -> str:
    values = []
    if isinstance(user, dict):
        if isinstance(groups := user.get("groups"), list):
            values = groups
    return ", ".join(values)


if __name__ == "__main__":
    main()
