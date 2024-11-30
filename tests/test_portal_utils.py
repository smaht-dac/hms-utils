import io
import json
import os
from hms_utils.portal.portal_utils import group_items_by, group_items_by_groupings
from hms_utils.dictionary_utils import compare_dictionaries_ordered

TESTS_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def test_portal_utils_a():

    file = os.path.join(TESTS_DATA_DIR, "files_for_portal_utils_group_item_by_testing.json")
    with io.open(file, "r") as f:
        items = json.load(f)

    # The above file has these in summary for our purposes ...
    #
    # - c53931bc-e3dc-4a37-97f3-05ffa2dc438b
    #   - donors: ST004
    #   - description: WGS Illumina NovaSeq X bam
    #
    # - dbba7681-88ea-4a09-884d-ff64cc6c557a
    #   - cell-line: HG002, HG00438, HG005, HG02257, HG02486, HG02622
    #   - description: WGS Illumina NovaSeq X bam
    #
    # - f2584000-f810-44b6-8eb7-855298c58eb3
    #   - cell-lines: HG002, HG00438, HG005, HG02257, HG02486, HG02622
    #   - description: WGS ONT PromethION 24 bam
    #
    # - 1a5b9cea-104e-45f3-9bef-8ed06aeede24
    #   - donors: ST003
    #   - description: WGS Illumina NovaSeq X bam
    #
    # - ea0f5f17-5753-42ed-b141-186e8261c58e
    #   - cell-lines: COLO829T
    #   - donors: DAC_DONOR_COLO829
    #   - description: WGS Illumina NovaSeq X bam
    #
    # - f9cc4a7a-9508-441b-91f2-99530f8c82c7
    #   - cell-lines: COLO829T
    #   - donors: DAC_DONOR_COLO829
    #   - description: WGS Illumina NovaSeq X bam
    #
    # - 3dccda14-8b17-4157-b3e6-4d9f1fafda5f
    #   - cell-lines: COLO829BL
    #   - donors: DAC_DONOR_COLO829
    #   - description: Fiber-seq PacBio Revio bam
    #
    # - 4cd1dff1-ceda-48c7-824e-26c43906083a
    #   - cell-lines: COLO829BL
    #   - donors: DAC_DONOR_COLO829, DAC_DONOR_COLO829_001
    #   - description: WGS Illumina NovaSeq X bam
    #
    # - fffceff8-4283-485d-b7ab-0cc19d3d1fa7
    #   - cell-lines: COLO829T
    #   - donors: DAC_DONOR_COLO829, DAC_DONOR_COLO829_001
    #   - description: WGS Illumina NovaSeq X bam
    #
    # - bdfb8964-1102-4baa-bd54-52b2feda4b03
    #   - cell-lines: COLO829BL
    #   - donors: DAC_DONOR_COLO829
    #   - description: Fiber-seq PacBio Revio bam
    #
    # Grouped by cell-lines ...
    #
    # - HG002
    #   - dbba7681-88ea-4a09-884d-ff64cc6c557a
    #   - f2584000-f810-44b6-8eb7-855298c58eb3
    # - HG00438
    #   - dbba7681-88ea-4a09-884d-ff64cc6c557a
    #   - f2584000-f810-44b6-8eb7-855298c58eb3
    # - HG005
    #   - dbba7681-88ea-4a09-884d-ff64cc6c557a
    #   - f2584000-f810-44b6-8eb7-855298c58eb3
    # - HG02257
    #   - dbba7681-88ea-4a09-884d-ff64cc6c557a
    #   - f2584000-f810-44b6-8eb7-855298c58eb3
    # - HG02486
    #   - dbba7681-88ea-4a09-884d-ff64cc6c557a
    #   - f2584000-f810-44b6-8eb7-855298c58eb3
    # - HG02622
    #   - dbba7681-88ea-4a09-884d-ff64cc6c557a
    #   - f2584000-f810-44b6-8eb7-855298c58eb3
    # - ST003
    #   - 1a5b9cea-104e-45f3-9bef-8ed06aeede24
    # - ST004
    #   - c53931bc-e3dc-4a37-97f3-05ffa2dc438b
    # - COLO829T
    #   - ea0f5f17-5753-42ed-b141-186e8261c58e
    #   - f9cc4a7a-9508-441b-91f2-99530f8c82c7
    #   - fffceff8-4283-485d-b7ab-0cc19d3d1fa7
    # - COLO829BL
    #   - 3dccda14-8b17-4157-b3e6-4d9f1fafda5f
    #   - 4cd1dff1-ceda-48c7-824e-26c43906083a
    #   - bdfb8964-1102-4baa-bd54-52b2feda4b03
    #
    # Grouped by donors ...
    #
    # - DAC_DONOR_COLO829
    #   - ea0f5f17-5753-42ed-b141-186e8261c58e
    #   - f9cc4a7a-9508-441b-91f2-99530f8c82c7
    #   - 3dccda14-8b17-4157-b3e6-4d9f1fafda5f
    #   - 4cd1dff1-ceda-48c7-824e-26c43906083a
    #   - fffceff8-4283-485d-b7ab-0cc19d3d1fa7
    #   - bdfb8964-1102-4baa-bd54-52b2feda4b03
    # - DAC_DONOR_COLO829_001
    #   - 4cd1dff1-ceda-48c7-824e-26c43906083a
    #   - fffceff8-4283-485d-b7ab-0cc19d3d1fa7
    #
    # Grouped by description ...
    #
    # - WGS Illumina NovaSeq X bam
    #   - c53931bc-e3dc-4a37-97f3-05ffa2dc438b
    #   - dbba7681-88ea-4a09-884d-ff64cc6c557a
    #   - 1a5b9cea-104e-45f3-9bef-8ed06aeede24
    #   - ea0f5f17-5753-42ed-b141-186e8261c58e
    #   - f9cc4a7a-9508-441b-91f2-99530f8c82c7
    #   - 4cd1dff1-ceda-48c7-824e-26c43906083a
    #   - fffceff8-4283-485d-b7ab-0cc19d3d1fa7
    # - WGS ONT PromethION 24 bam
    #   - f2584000-f810-44b6-8eb7-855298c58eb3
    # - Fiber-seq PacBio Revio bam
    #   - 3dccda14-8b17-4157-b3e6-4d9f1fafda5f
    #   - bdfb8964-1102-4baa-bd54-52b2feda4b03

    GROUPING_CELL_LINES = "file_sets.libraries.analytes.samples.sample_sources.cell_line.code"
    GROUPING_DONORS = "donors.display_title"
    GROUPING_FILE_DESCRIPTOR = "release_tracker_description"

    assert group_items_by(items, GROUPING_CELL_LINES, identifying_property="uuid") == {
        "group": "file_sets.libraries.analytes.samples.sample_sources.cell_line.code",
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
        "group": "donors.display_title",
        "item_count": 10,
        "group_count": 5,
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
            ],
            "DAC_DONOR_COLO829_001": [
                "4cd1dff1-ceda-48c7-824e-26c43906083a"
            ]
        }
    }

    assert group_items_by(items, GROUPING_FILE_DESCRIPTOR, identifying_property="uuid") == {
        "group": "release_tracker_description",
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

    groupings = [
        GROUPING_CELL_LINES,
        GROUPING_DONORS,
        GROUPING_FILE_DESCRIPTOR
    ]
    result = group_items_by_groupings(items, groupings, identifying_property="uuid", sort=True)
    expected_result = {
        "group": "file_sets.libraries.analytes.samples.sample_sources.cell_line.code",
        "item_count": 10,
        "group_count": 9,
        "group_items": {
            "COLO829BL": {
                "group": "donors.display_title",
                "item_count": 3,
                "group_count": 2,
                "group_items": {
                    "DAC_DONOR_COLO829": {
                        "group": "release_tracker_description",
                        "item_count": 3,
                        "group_count": 2,
                        "group_items": {
                            "Fiber-seq PacBio Revio bam": [
                                "3dccda14-8b17-4157-b3e6-4d9f1fafda5f",
                                "bdfb8964-1102-4baa-bd54-52b2feda4b03"
                            ],
                            "WGS Illumina NovaSeq X bam": [
                                "4cd1dff1-ceda-48c7-824e-26c43906083a"
                            ]
                        }
                    },
                    "DAC_DONOR_COLO829_001": {
                        "group": "release_tracker_description",
                        "item_count": 1,
                        "group_count": 1,
                        "group_items": {
                            "WGS Illumina NovaSeq X bam": [
                                "4cd1dff1-ceda-48c7-824e-26c43906083a"
                            ]
                        }
                    }
                }
            },
            "COLO829T": {
                "group": "donors.display_title",
                "item_count": 3,
                "group_count": 1,
                "group_items": {
                    "DAC_DONOR_COLO829": {
                        "group": "release_tracker_description",
                        "item_count": 3,
                        "group_count": 1,
                        "group_items": {
                            "WGS Illumina NovaSeq X bam": [
                                "ea0f5f17-5753-42ed-b141-186e8261c58e",
                                "f9cc4a7a-9508-441b-91f2-99530f8c82c7",
                                "fffceff8-4283-485d-b7ab-0cc19d3d1fa7"
                            ]
                        }
                    }
                }
            },
            None: {
                "group": "donors.display_title",
                "item_count": 2,
                "group_count": 2,
                "group_items": {
                    "ST003": {
                        "group": "release_tracker_description",
                        "item_count": 1,
                        "group_count": 1,
                        "group_items": {
                            "WGS Illumina NovaSeq X bam": [
                                "1a5b9cea-104e-45f3-9bef-8ed06aeede24"
                            ]
                        }
                    },
                    "ST004": {
                        "group": "release_tracker_description",
                        "item_count": 1,
                        "group_count": 1,
                        "group_items": {
                            "WGS Illumina NovaSeq X bam": [
                                "c53931bc-e3dc-4a37-97f3-05ffa2dc438b"
                            ]
                        }
                    }
                }
            },
            "HG002": {
                "group": "donors.display_title",
                "item_count": 2,
                "group_count": 1,
                "group_items": {
                    None: {
                        "group": "release_tracker_description",
                        "item_count": 2,
                        "group_count": 2,
                        "group_items": {
                            "WGS Illumina NovaSeq X bam": [
                                "dbba7681-88ea-4a09-884d-ff64cc6c557a"
                            ],
                            "WGS ONT PromethION 24 bam": [
                                "f2584000-f810-44b6-8eb7-855298c58eb3"
                            ]
                        }
                    }
                }
            },
            "HG00438": {
                "group": "donors.display_title",
                "item_count": 2,
                "group_count": 1,
                "group_items": {
                    None: {
                        "group": "release_tracker_description",
                        "item_count": 2,
                        "group_count": 2,
                        "group_items": {
                            "WGS Illumina NovaSeq X bam": [
                                "dbba7681-88ea-4a09-884d-ff64cc6c557a"
                            ],
                            "WGS ONT PromethION 24 bam": [
                                "f2584000-f810-44b6-8eb7-855298c58eb3"
                            ]
                        }
                    }
                }
            },
            "HG005": {
                "group": "donors.display_title",
                "item_count": 2,
                "group_count": 1,
                "group_items": {
                    None: {
                        "group": "release_tracker_description",
                        "item_count": 2,
                        "group_count": 2,
                        "group_items": {
                            "WGS Illumina NovaSeq X bam": [
                                "dbba7681-88ea-4a09-884d-ff64cc6c557a"
                            ],
                            "WGS ONT PromethION 24 bam": [
                                "f2584000-f810-44b6-8eb7-855298c58eb3"
                            ]
                        }
                    }
                }
            },
            "HG02257": {
                "group": "donors.display_title",
                "item_count": 2,
                "group_count": 1,
                "group_items": {
                    None: {
                        "group": "release_tracker_description",
                        "item_count": 2,
                        "group_count": 2,
                        "group_items": {
                            "WGS Illumina NovaSeq X bam": [
                                "dbba7681-88ea-4a09-884d-ff64cc6c557a"
                            ],
                            "WGS ONT PromethION 24 bam": [
                                "f2584000-f810-44b6-8eb7-855298c58eb3"
                            ]
                        }
                    }
                }
            },
            "HG02486": {
                "group": "donors.display_title",
                "item_count": 2,
                "group_count": 1,
                "group_items": {
                    None: {
                        "group": "release_tracker_description",
                        "item_count": 2,
                        "group_count": 2,
                        "group_items": {
                            "WGS Illumina NovaSeq X bam": [
                                "dbba7681-88ea-4a09-884d-ff64cc6c557a"
                            ],
                            "WGS ONT PromethION 24 bam": [
                                "f2584000-f810-44b6-8eb7-855298c58eb3"
                            ]
                        }
                    }
                }
            },
            "HG02622": {
                "group": "donors.display_title",
                "item_count": 2,
                "group_count": 1,
                "group_items": {
                    None: {
                        "group": "release_tracker_description",
                        "item_count": 2,
                        "group_count": 2,
                        "group_items": {
                            "WGS Illumina NovaSeq X bam": [
                                "dbba7681-88ea-4a09-884d-ff64cc6c557a"
                            ],
                            "WGS ONT PromethION 24 bam": [
                                "f2584000-f810-44b6-8eb7-855298c58eb3"
                            ]
                        }
                    }
                }
            }
        }
    }
    assert result == expected_result
    assert compare_dictionaries_ordered(result, expected_result)
