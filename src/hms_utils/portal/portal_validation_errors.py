from dcicutils.ff_utils import search_metadata
from dcicutils.portal_utils import Portal
from hms_utils.argv import ARGV
from hms_utils.chars import chars


def main():

    argv = ARGV({
        ARGV.REQUIRED(str): "--env"
    })

    portal = Portal(argv.env)
    query = "/search/?type=Item&validation_errors.name%21=No+value"
    ignored_types = ["AccessKey", "TrackingItem", "Consortium", "SubmissionCenter"]
    results = search_metadata(query, key=portal.key, is_generator=True)

    for item in results:
        if isinstance(item, dict) and (item_uuid := item.get("uuid")):
            if (item_type := portal.get_schema_type(item)) not in ignored_types:
                print(f"{item_uuid}: {item_type}")
                if item := portal.get_metadata(item_uuid):
                    if errors := item.get("validation-errors"):
                        for error in errors:
                            print(f"{chars.rarrow_hollow} ERROR: {error.get('description')}")


if __name__ == "__main__":
    main()
    pass
