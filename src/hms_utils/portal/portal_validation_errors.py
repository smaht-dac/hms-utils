from dcicutils.ff_utils import search_metadata
from hms_utils.portal.portal_utils import Portal
from hms_utils.argv import ARGV
from hms_utils.chars import chars


def main():

    argv = ARGV({
        ARGV.REQUIRED(str): "--env",
        ARGV.OPTIONAL(bool): ["--details", "--detail", "--verbose"],
        ARGV.OPTIONAL(bool): "--sid",
        ARGV.OPTIONAL(bool): "--sid-reindex",
        ARGV.OPTIONAL([str]): "uuids"
    })

    portal = Portal(argv.env)
    status = 0
    uuids_with_sid_error = []

    if argv.uuids:
        for uuid in argv.uuids:
            if item := portal.get_metadata(uuid):
                if _check_for_validation_errors(item, sid=argv.sid):
                    if argv.sid and argv.sid_reindex:
                        uuids_with_sid_error.append(item.get("uuid"))
                    status

    else:
        query = "/search/?type=Item&validation_errors.name%21=No+value&limit=100000"
        ignored_types = []
        for item in search_metadata(query, key=portal.key, is_generator=True):
            if isinstance(item, dict) and (item_uuid := item.get("uuid")):
                if (item_type := portal.get_schema_type(item)) not in ignored_types:
                    print(f"{item_uuid}: {item_type}")
                    status = 1
                    if argv.sid or argv.sid_reindex or argv.details:
                        if item := portal.get_metadata(item_uuid):
                            if _check_for_validation_errors(item, sid=argv.sid):
                                if argv.sid and argv.sid_reindex:
                                    uuids_with_sid_error.append(item.get("uuid"))

    if uuids_with_sid_error:
        for uuid_with_sid_error in uuids_with_sid_error:
            print(f"Reindexing item with sid error : {uuid_with_sid_error}")
            portal.reindex_metadata(uuid_with_sid_error)

    exit(status)


def _check_for_validation_errors(item: dict, sid: bool = False) -> bool:
    found = False
    if errors := item.get("validation-errors"):
        for error in errors:
            if (sid is not True) or ("sid" in str(error)):
                found = True
                print(f"{chars.rarrow_hollow} ERROR: {error.get('description')}")
    return found


if __name__ == "__main__":
    main()
    pass
