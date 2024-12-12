import os
from typing import Optional
from hms_utils.misc_utils import dj
from hms_utils.portal.portal_utils import create_pyramid_request_for_testing, Portal
from encoded.recent_files_summary import recent_files_summary, print_normalized_aggregation_results


def test():

    request_args = {
        "nmonths": 18,
        "include_current_month": "true",
        # "date_property_name": "date_created",
        # "nocells": False,  # N.B. default is True
        # "legacy": True,
        # "nomixtures": True,
        # "favor_donor": True,
        # "include_missing": True,
        # "willrfix": True,
        "troubleshoot": True,
        "troubleshoot_elasticsearch": True,
        "debug": True,
    }

    def request_embed(query: str, as_user: Optional[str] = None) -> Optional[dict]:
        nonlocal portal
        return portal.get_metadata(query)

    portal = Portal(os.path.expanduser("~/repos/smaht-portal/development.ini"))
    request = create_pyramid_request_for_testing(portal.vapp, request_args)
    request.embed = request_embed

    results = recent_files_summary(request)

    print("\n>>> RAW RESULTS <<<\n")
    dj(results)
    print("\n>>> FORMATTED RESULTS <<<\n")
    print_normalized_aggregation_results(results, uuids=False, nobold=True)
    print("\n>>> DETAILED FORMATTED RESULTS <<<\n")
    print_normalized_aggregation_results(results, uuids=True, uuid_details=True)


test()
