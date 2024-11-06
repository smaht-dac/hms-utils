from dcicutils.ff_utils import search_metadata
from dcicutils.portal_utils import Portal
from hms_utils.argv import ARGV


def main():

    argv = ARGV({
        ARGV.REQUIRED(str): ["--env", ARGV.DEFAULT, "smaht-local"]
    })

    portal = Portal(argv.env)
    status = 0

    query = "/search/?type=Item&consortia.display_title=No+value&limit=1000000"
    ignored_types = ["AccessKey", "TrackingItem", "Consortium", "SubmissionCenter"]
    total = 0
    for item in search_metadata(query, key=portal.key, is_generator=True):
        item_type = portal.get_schema_type(item)
        if item_type in ignored_types:
            continue
        item_uuid = item.get("uuid")
        print(f"{item_uuid}: {item_type}")
        total += 1

    print(f"TOTAL: {total}")
    exit(status)


if __name__ == "__main__":
    main()
    pass
