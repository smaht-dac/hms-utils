import json
import sys
from typing import List
from hms_utils.argv import ARGV
from hms_utils.portal.portal_utils import Portal as Portal
from hms_utils.type_utils import is_uuid


def main():

    argv = ARGV({
        ARGV.OPTIONAL(str): ["--env"],
        ARGV.REQUIRED(str): ["user"],
        ARGV.OPTIONAL([str]): ["--consortia", "--consortium", "--c"],
        ARGV.OPTIONAL([str]): ["--submission-centers", "--submission-center", "--sc", "--s"],
        ARGV.OPTIONAL(bool): ["--verbose"],
        ARGV.OPTIONAL(bool): ["--debug"],
        ARGV.OPTIONAL(bool): ["--ping"]
    })

    portal = Portal.create(argv.env, verbose=argv.verbose, debug=argv.debug, ping=argv.ping)

    user_query = f"/users/{argv.user}"
    if not (user := portal.get_metadata(user_query)):
        print("Cannot find user: {argv.user")

    consortia = None
    if argv.consortia:
        if (len(argv.consortia) == 1) and (argv.consortia[0].lower() in ["none", "null", "no", "empty"]):
            if argv.verbose:
                print(f"Removing consortia for {argv.user}")
            portal.delete_metadata_property(user_query, "consortia")
        else:
            if (consortia := _get_consortia(portal, argv.consortia)):
                if argv.verbose:
                    print(f"Setting consortia for {argv.user} to: {', '.join(consortia)}")
                portal.patch_metadata(user_query, {"consortia": consortia})

    submission_centers = None
    if argv.submission_centers:
        if (len(argv.submission_centers) == 1) and (argv.submission_centers[0] in ["none", "null", "no", "empty"]):
            # Deleting submission_centers does not seem to work; set it to empty list instead.
            # portal.delete_metadata_property(user_query, "submission_centers")
            if argv.verbose:
                print(f"Removing submission-centers for {argv.user}")
            portal.patch_metadata(user_query, {"submission_centers": []})
        else:
            if (submission_centers := _get_submission_centers(portal, argv.submission_centers)):
                if argv.verbose:
                    print(f"Setting submission-centers for {argv.user} to: {', '.join(submission_centers)}")
                portal.patch_metadata(user_query, {"submission_centers": submission_centers})

    user = portal.get_metadata(user_query, raw=True, database=True)
    print(json.dumps(user, indent=4))


def _get_consortia(portal: Portal, values: List[str]) -> List[str]:
    return _get_affiliations(portal, values, "consortia")


def _get_submission_centers(portal: Portal, values: List[str]) -> List[str]:
    return _get_affiliations(portal, values, "submission-centers")


def _get_affiliations(portal: Portal, values: List[str], affiliation_name: str) -> List[str]:
    values_found = []
    if isinstance(values, list):
        for value in values:
            if isinstance(value, str):
                if ((value_found := portal.get_metadata(f"/{affiliation_name}/{value}", raise_exception=False)) and
                    is_uuid(value_found_uuid := value_found.get("uuid"))):  # noqa
                    values_found.append(value_found_uuid)
                else:
                    print(f"WARNING: Specified value ({affiliation_name}) not found: {value}", file=sys.stderr)
    return values_found


if __name__ == "__main__":
    main()
