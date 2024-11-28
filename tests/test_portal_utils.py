import io
import json
import os
from hms_utils.portal.portal_utils import group_items_by, group_items_by_groupings  # noqa

TESTS_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def test_portal_utils_a():

    file = os.path.join(TESTS_DATA_DIR, "files_for_portal_utils_group_item_by_testing.json")
    with io.open(file, "r") as f:
        items = json.load(f)

    GROUPING_CELL_LINES = "file_sets.libraries.analytes.samples.sample_sources.cell_line.code"
    GROUPING_DONORS = "donors.display_title"
    GROUPING_FILE_DESCRIPTOR = "release_tracker_description"

    assert group_items_by(items, GROUPING_CELL_LINES, identifying_property="uuid") == {
        "group_name": "file_sets.libraries.analytes.samples.sample_sources.cell_line.code",
        "item_count": 10,
        "group_count": 9,
        "group_items": {
            None: [
                "c53931bc-e3dc-4a37-97f3-05ffa2dc438b",
                "1a5b9cea-104e-45f3-9bef-8ed06aeede24"
            ],
            "HG00438": [
                "dbba7681-88ea-4a09-884d-ff64cc6c557a",
                "f2584000-f810-44b6-8eb7-855298c58eb3"
            ],
            "HG02486": [
                "dbba7681-88ea-4a09-884d-ff64cc6c557a",
                "f2584000-f810-44b6-8eb7-855298c58eb3"
            ],
            "HG02622": [
                "dbba7681-88ea-4a09-884d-ff64cc6c557a",
                "f2584000-f810-44b6-8eb7-855298c58eb3"
            ],
            "HG005": [
                "dbba7681-88ea-4a09-884d-ff64cc6c557a",
                "f2584000-f810-44b6-8eb7-855298c58eb3"
            ],
            "HG02257": [
                "dbba7681-88ea-4a09-884d-ff64cc6c557a",
                "f2584000-f810-44b6-8eb7-855298c58eb3"
            ],
            "HG002": [
                "dbba7681-88ea-4a09-884d-ff64cc6c557a",
                "f2584000-f810-44b6-8eb7-855298c58eb3"
            ],
            "COLO829T": [
                "ea0f5f17-5753-42ed-b141-186e8261c58e",
                "f9cc4a7a-9508-441b-91f2-99530f8c82c7",
                "fffceff8-4283-485d-b7ab-0cc19d3d1fa7"
            ],
            "COLO829BL": [
                "3dccda14-8b17-4157-b3e6-4d9f1fafda5f",
                "4cd1dff1-ceda-48c7-824e-26c43906083a",
                "bdfb8964-1102-4baa-bd54-52b2feda4b03"
            ]
        }
    }

    assert group_items_by(items, GROUPING_DONORS, identifying_property="uuid") == {
        "group_name": "donors.display_title",
        "item_count": 10,
        "group_count": 4,
        "group_items": {
            None: [
                "dbba7681-88ea-4a09-884d-ff64cc6c557a",
                "f2584000-f810-44b6-8eb7-855298c58eb3"
            ],
            "ST004": [
                "c53931bc-e3dc-4a37-97f3-05ffa2dc438b"
            ],
            "ST003": [
                "1a5b9cea-104e-45f3-9bef-8ed06aeede24"
            ],
            "DAC_DONOR_COLO829": [
                "ea0f5f17-5753-42ed-b141-186e8261c58e",
                "f9cc4a7a-9508-441b-91f2-99530f8c82c7",
                "3dccda14-8b17-4157-b3e6-4d9f1fafda5f",
                "4cd1dff1-ceda-48c7-824e-26c43906083a",
                "fffceff8-4283-485d-b7ab-0cc19d3d1fa7",
                "bdfb8964-1102-4baa-bd54-52b2feda4b03"
            ]
        }
    }

    assert group_items_by(items, GROUPING_FILE_DESCRIPTOR, identifying_property="uuid") == {
        "group_name": "release_tracker_description",
        "item_count": 10,
        "group_count": 3,
        "group_items": {
            "WGS Illumina NovaSeq X bam": [
                "c53931bc-e3dc-4a37-97f3-05ffa2dc438b",
                "dbba7681-88ea-4a09-884d-ff64cc6c557a",
                "1a5b9cea-104e-45f3-9bef-8ed06aeede24",
                "ea0f5f17-5753-42ed-b141-186e8261c58e",
                "f9cc4a7a-9508-441b-91f2-99530f8c82c7",
                "4cd1dff1-ceda-48c7-824e-26c43906083a",
                "fffceff8-4283-485d-b7ab-0cc19d3d1fa7"
            ],
            "WGS ONT PromethION 24 bam": [
                "f2584000-f810-44b6-8eb7-855298c58eb3"
            ],
            "Fiber-seq PacBio Revio bam": [
                "3dccda14-8b17-4157-b3e6-4d9f1fafda5f",
                "bdfb8964-1102-4baa-bd54-52b2feda4b03"
            ]
        }
    }

    # assert grouped_items == expected_grouped_items
    # grouped_items = group_items_by_groupings(items, groupings, identifying_property="uuid")
    # import pdb ; pdb.set_trace()  # noqa
    # pass
