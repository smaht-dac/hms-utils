from dcicutils.ff_utils import search_metadata
from dcicutils.portal_utils import Portal
from hms_utils.argv import ARGV
from hms_utils.chars import chars


def main():

    argv = ARGV({
        ARGV.REQUIRED(str): "--env",
        ARGV.OPTIONAL([str]): "uuids"
    })

    portal = Portal(argv.env)
    status = 0

    if argv.uuids:
        for uuid in argv.uuids:
            if item := portal.get_metadata(uuid):
                if _check_for_validation_errors(item):
                    status
        exit(status)

    query = "/search/?type=Item&validation_errors.name%21=No+value"
    ignored_types = []
    for item in search_metadata(query, key=portal.key, is_generator=True):
        if isinstance(item, dict) and (item_uuid := item.get("uuid")):
            if (item_type := portal.get_schema_type(item)) not in ignored_types:
                print(f"{item_uuid}: {item_type}")
                if item := portal.get_metadata(item_uuid):
                    if _check_for_validation_errors(item):
                        status = 1
    exit(status)


def _check_for_validation_errors(item: dict) -> bool:
    if errors := item.get("validation-errors"):
        for error in errors:
            print(f"{chars.rarrow_hollow} ERROR: {error.get('description')}")


if __name__ == "__main__":
    main()
    pass
