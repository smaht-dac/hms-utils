from copy import deepcopy
import json
import sys
from typing import List, Optional, Union
import unicodedata
from dcicutils.structured_data import StructuredDataSet
from dcicutils.portal_utils import Portal
from hms_utils.dictionary_utils import sort_dictionary
from hms_utils.chars import chars


class PROPERTY:
    LAST_NAME = "last_name"
    FIRST_NAME = "first_name"
    EMAIL = "email"
    SUBMISSION_CENTER = "submission_center"
    SUBMISSION_CENTERS = "submission_centers"
    SUBMITS_FOR = "submits_for"
    REVOKED = "revoked"
    STATUS = "status"


USER_SPREADSHEET_COLUMN_MAP = {
    "Dana Farber Cancer Institute, Harvard Medical School": None,
    "SMaHT Listed Last Name": PROPERTY.LAST_NAME,
    "SMaHT Listed First Name": PROPERTY.FIRST_NAME,
    "Email": PROPERTY.EMAIL,
    "SMaHT Contact PI Association": None,
    "Grant Component": None,
    "DAC code in the portal": PROPERTY.SUBMISSION_CENTER,
    "Data submitter": PROPERTY.SUBMITS_FOR,
    "Revoked": PROPERTY.REVOKED
}


def sanity_check_users_from_spreadsheet_with_portal(file_or_users: Union[str, List[dict]],
                                                    portal_or_portal_env: Union[str, Portal],
                                                    verbose: bool = False,
                                                    debug: bool = False) -> None:

    def print_diffs_by_kind(diffs_by_kind: dict) -> None:
        if diffs_by_kind:
            for diff in diffs_by_kind:
                print(f"{chars.rarrow_hollow} {diff}")
                for user in diffs_by_kind[diff]:
                    print(f"  - {user['email']} {chars.dot} {user['uuid']}")

    diffs_by_kind = {}

    if isinstance(portal_or_portal_env, str):
        portal = Portal(portal_or_portal_env)
    elif not isinstance(portal := portal_or_portal_env, Portal):
        return
    if isinstance(file_or_users, str):
        users = read_users_from_spreadsheet(file_or_users)
    elif not isinstance(users := file_or_users, list):
        return

    users_to_add = []
    users_to_update = []
    for user in users:
        try:
            user_metadata = portal.get_metadata(f"/users/{user[PROPERTY.EMAIL]}")
            user_portal = get_user_from_portal_metadata(user_metadata)
            if debug is True:
                _debug(f"Read user from portal OK: {user[PROPERTY.EMAIL]}")
            if users_are_equal(user, user_portal):
                if verbose is True:
                    _info(f"User from spreadsheet and portal are the SAME: {user[PROPERTY.EMAIL]}")
            else:
                users_to_update.append(user)
                _error(f"User from spreadsheet and portal are DIFFERENT:"
                       f" {user[PROPERTY.EMAIL]} {chars.dot} {user_portal['uuid']}")
                diffs = compile_diffs(user, user_portal)
                for diff in diffs:
                    if diff not in diffs_by_kind:
                        diffs_by_kind[diff] = []
                    diffs_by_kind[diff].append({"email": user[PROPERTY.EMAIL], "uuid": user_portal["uuid"]})
                if debug is True:
                    _error(f"{chars.rarrow} SPREADSHEET: {user}")
                    _error(f"{chars.rarrow} PORTAL:      {user_portal}")
        except Exception as e:
            if ("not" in str(e).lower()) and ("found" in str(e).lower()):
                _error(f"User from spreadsheet is MISSING in portal: {user[PROPERTY.EMAIL]}")
                users_to_add.append(user)
            else:
                _error(f"Cannot read user from portal: {user[PROPERTY.EMAIL]}")
                _error(str(e))

    print_diffs_by_kind(diffs_by_kind)
    return users_to_add, users_to_update


def read_users_from_spreadsheet(file: str):
    data = StructuredDataSet(file)
    data = data.data
    data = next(iter(data.values()))
    users = []
    for item in data:
        users_from_spreadsheet_row = get_user_from_spreadsheet_row(item)
        for user_from_spreadsheet_row in users_from_spreadsheet_row:
            users.append(user_from_spreadsheet_row)
    return users


def get_user_from_spreadsheet_row(row: object) -> List[dict]:
    # Returns zero or more user dictionaries for the given spreadsheet row.
    # Can return more than one if there are more than one email in the email field.
    user = {}
    for spreadsheet_column_name in USER_SPREADSHEET_COLUMN_MAP:
        if user_column_name := USER_SPREADSHEET_COLUMN_MAP.get(spreadsheet_column_name):
            if spreadsheet_column_value := row.get(spreadsheet_column_name):
                user[user_column_name] = normalize_string(spreadsheet_column_value)
            else:
                user[user_column_name] = ""
    user[PROPERTY.EMAIL] = user[PROPERTY.EMAIL].lower()
    user[PROPERTY.SUBMISSION_CENTERS] = map_spreadsheet_submission_centers(user[PROPERTY.SUBMISSION_CENTER])
    del user[PROPERTY.SUBMISSION_CENTER]
    if user[PROPERTY.SUBMITS_FOR].lower() in ["yes", "y", "true"]:
        user[PROPERTY.SUBMITS_FOR] = user[PROPERTY.SUBMISSION_CENTERS]
    else:
        user[PROPERTY.SUBMITS_FOR] = []
    user[PROPERTY.STATUS] = "deleted" if (user[PROPERTY.REVOKED].lower() in ["yes", "y", "true"]) else "current"
    del user[PROPERTY.REVOKED]
    users = [user := sort_dictionary(user)]
    if "," in user[PROPERTY.EMAIL]:
        # Handle multiple (comma-separated) emails within a single field;
        # e.g.: abyzov.alexej@mayo.edu, alexej.abyzov@yale.edu
        if len(user_emails := list(set([item.strip() for item in user["email"].split(",")]))) > 1:
            user[PROPERTY.EMAIL] = user_emails[0]
            for user_email in user_emails[1:]:
                user = deepcopy(user)
                user[PROPERTY.EMAIL] = user_email.lower()
                users.append(user)
    if not user[PROPERTY.SUBMISSION_CENTERS]:
        del user[PROPERTY.SUBMISSION_CENTERS]
    if not user[PROPERTY.SUBMITS_FOR]:
        del user[PROPERTY.SUBMITS_FOR]
    return users


def map_spreadsheet_submission_centers(submission_centers: List[str]) -> List[str]:
    mapped_submission_centers = []
    if isinstance(submission_centers, str):
        submission_centers = submission_centers.split(",")
    if isinstance(submission_centers, list):
        for submission_center in submission_centers:
            if isinstance(submission_center, str) and (submission_center := submission_center.strip()):
                if submission_center.lower() == "dac":
                    submission_center = "smaht_dac"
                elif submission_center.lower() == "nih":
                    submission_center = None
                if submission_center and (submission_center not in mapped_submission_centers):
                    mapped_submission_centers.append(submission_center)
    return sorted(mapped_submission_centers)


def get_user_from_portal_metadata(user_metadata: dict) -> Optional[dict]:
    if isinstance(user_metadata, dict):
        user = {}
        user[PROPERTY.EMAIL] = normalize_string(user_metadata.get("email", ""))
        user[PROPERTY.FIRST_NAME] = normalize_string(user_metadata.get("first_name", ""))
        user[PROPERTY.LAST_NAME] = normalize_string(user_metadata.get("last_name", ""))
        # user[PROPERTY.REVOKED] = user_metadata.get("status", "").lower() in ["deleted", "revoked"]
        user[PROPERTY.STATUS] = user_metadata.get("status", "")
        user["uuid"] = user_metadata.get("uuid", "")
        if isinstance(submission_centers := user_metadata.get("submission_centers", []), list):
            user[PROPERTY.SUBMISSION_CENTERS] = \
                sorted(list(set([item.get("identifier", "") for item in submission_centers if item.get("identifier")])))
        if isinstance(submits_for := user_metadata.get("submits_for", []), list):
            user[PROPERTY.SUBMITS_FOR] = \
                sorted(list(set([item["identifier"] for item in submits_for if item.get("identifier")])))
        if not user[PROPERTY.SUBMISSION_CENTERS]:
            del user[PROPERTY.SUBMISSION_CENTERS]
        if not user[PROPERTY.SUBMITS_FOR]:
            del user[PROPERTY.SUBMITS_FOR]
        return sort_dictionary(user)
    return None


def get_nth_value_in_dictionary(data: dict, nth: int) -> str:
    if isinstance(data, dict) and isinstance(nth, int) and nth >= 0:
        try:
            if nth < len(keys := list(data.keys())):
                if isinstance(value := data[keys[nth]], str):
                    return normalize_string(value)
        except Exception:
            pass
    return ""


def users_are_equal(user_from_spreadsheet: dict, user_from_portal: dict, indent: int = 0):
    user_from_spreadsheet = deepcopy(user_from_spreadsheet)
    user_from_spreadsheet[PROPERTY.EMAIL] = user_from_spreadsheet[PROPERTY.EMAIL].lower()
    user_from_portal = deepcopy(user_from_portal)
    user_from_portal[PROPERTY.EMAIL] = user_from_portal[PROPERTY.EMAIL].lower()
    del user_from_portal["uuid"]
    return user_from_spreadsheet == user_from_portal


def compile_diffs(user_from_spreadsheet: dict, user_from_portal: dict) -> List[str]:
    diffs = []
    if isinstance(user_from_spreadsheet, dict) and isinstance(user_from_portal, dict):
        for key in user_from_spreadsheet:
            spreadsheet_value = user_from_spreadsheet[key]
            portal_value = user_from_portal.get(key)
            if portal_value is None:
                diffs.append(f"MISSING: {key} {chars.dot} SPREADSHEET: {spreadsheet_value}")
            elif portal_value != spreadsheet_value:
                diffs.append(f"DIFF: {key} {chars.dot} SPREADSHEET: {spreadsheet_value}"
                             f" {chars.dot} PORTAL: {portal_value}")
        for key in user_from_portal:
            if key == "uuid":
                continue
            portal_value = user_from_portal[key]
            spreadsheet_value = user_from_spreadsheet.get(key)
            if spreadsheet_value is None:
                diffs.append(f"MISSING: {key} {chars.dot} PORTAL: {portal_value}")
    return diffs


def normalize_string(value: str) -> str:
    if isinstance(value, str):
        return "".join([c for c in unicodedata.normalize("NFD", value) if not unicodedata.combining(c)]).strip()
    return ""


def _debug(message: str) -> None:
    print("DEBUG: " + message, file=sys.stderr, flush=True)


def _info(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _error(message: str, plain: bool = False) -> None:
    print(("ERROR: " if plain is not True else "") + message, file=sys.stderr, flush=True)


# https://docs.google.com/spreadsheets/d/1WYc_UKkpVUUBPJPbZdwwBX28f6Qr5I9PblOdGqu7g1M/view?gid=446162554#gid=446162554
users_spreadsheet = "smaht_users_20241025.tsv"

portal_env = "smaht-data"
dump = False
process = True
verbose = True
debug = False

users = read_users_from_spreadsheet(users_spreadsheet)

if dump:
    print(json.dumps(users, indent=4))

if process:
    portal = Portal(portal_env)
    users_to_add, users_to_update = \
        sanity_check_users_from_spreadsheet_with_portal(users, portal, verbose=verbose, debug=debug)

if users_to_add:
    print("USERS TO ADD")
    print(json.dumps(users_to_add, indent=4))

if users_to_update:
    print("USERS TO UPDATE")
    print(json.dumps(users_to_update, indent=4))
