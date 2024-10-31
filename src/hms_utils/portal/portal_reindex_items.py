from hms_utils.portal.portal_utils import Portal
from hms_utils.argv import ARGV


def main():

    argv = ARGV({
        ARGV.REQUIRED(str): "--env",
        ARGV.REQUIRED([str]): "uuids"
    })

    portal = Portal(argv.env)
    if portal.reindex_metadata(argv.uuids):
        print("OK")
    else:
        print("ERROR")


if __name__ == "__main__":
    main()
    pass
