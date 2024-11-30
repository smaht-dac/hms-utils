import io
import json
import os
from hms_utils.dictionary_utils import group_items_by, group_items_by_groupings
from hms_utils.dictionary_utils import compare_dictionaries_ordered, get_properties


def test_get_properties_a():
    data = {
        "file_sets": [
            {
                "libraries": [
                    {
                        "analytes": [
                            {
                                "samples": [
                                    {
                                        "sample_sources": [
                                            {
                                                "cell_line": [
                                                    {
                                                        "code": "COLO829BL_1"
                                                    },
                                                    {
                                                        "code": "COLO829T_1"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "sample_sources": [
                                            {
                                                "cell_line": [
                                                    {
                                                        "code": "COLO829BL_2"
                                                    },
                                                    {
                                                        "code": "COLO829T_2"
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            },
                            {
                                "samples": [
                                    {
                                        "sample_sources": [
                                            {
                                                "cell_line": [
                                                    {
                                                        "code": "COLO829BL_3"
                                                    },
                                                    {
                                                        "code": "COLO829T_3"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "sample_sources": [
                                            {
                                                "cell_line": [
                                                    {
                                                        "code": "COLO829BL_4"
                                                    },
                                                    {
                                                        "code": "COLO829T_4"
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        "analytes": [
                            {
                                "samples": [
                                    {
                                        "sample_sources": [
                                            {
                                                "cell_line": [
                                                    {
                                                        "code": "COLO829BL_5"
                                                    },
                                                    {
                                                        "code": "COLO829T_5"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "sample_sources": [
                                            {
                                                "cell_line": [
                                                    {
                                                        "code": "COLO829BL_6"
                                                    },
                                                    {
                                                        "code": "COLO829T_6"
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            },
                            {
                                "samples": [
                                    {
                                        "sample_sources": [
                                            {
                                                "cell_line": [
                                                    {
                                                        "code": "COLO829BL_7"
                                                    },
                                                    {
                                                        "code": "COLO829T_7"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "sample_sources": [
                                            {
                                                "cell_line": [
                                                    {
                                                        "code": "COLO829BL_8"
                                                    },
                                                    {
                                                        "code": "COLO829T_8"
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
            {
                "libraries": [
                    {
                        "analytes": [
                            {
                                "samples": [
                                    {
                                        "sample_sources": [
                                            {
                                                "cell_line": [
                                                    {
                                                        "code": "COLO829BL_9"
                                                    },
                                                    {
                                                        "code": "COLO829T_9"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "sample_sources": [
                                            {
                                                "cell_line": [
                                                    {
                                                        "code": "COLO829BL_10"
                                                    },
                                                    {
                                                        "code": "COLO829T_10"
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            },
                            {
                                "samples": [
                                    {
                                        "sample_sources": [
                                            {
                                                "cell_line": [
                                                    {
                                                        "code": "COLO829BL_11"
                                                    },
                                                    {
                                                        "code": "COLO829T_11"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "sample_sources": [
                                            {
                                                "cell_line": [
                                                    {
                                                        "code": "COLO829BL_12"
                                                    },
                                                    {
                                                        "code": "COLO829T_12"
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        "analytes": [
                            {
                                "samples": [
                                    {
                                        "sample_sources": [
                                            {
                                                "cell_line": [
                                                    {
                                                        "code": "COLO829BL_13"
                                                    },
                                                    {
                                                        "code": "COLO829T_13"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "sample_sources": [
                                            {
                                                "cell_line": [
                                                    {
                                                        "code": "COLO829BL_14"
                                                    },
                                                    {
                                                        "code": "COLO829T_14"
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            },
                            {
                                "samples": [
                                    {
                                        "sample_sources": [
                                            {
                                                "cell_line": [
                                                    {
                                                        "code": "COLO829BL_15"
                                                    },
                                                    {
                                                        "code": "COLO829T_15"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "sample_sources": [
                                            {
                                                "cell_line": [
                                                    {
                                                        "code": "COLO829BL_16"
                                                    },
                                                    {
                                                        "code": "COLO829T_16"
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    }

    expected_result = sorted(["COLO829BL_1", "COLO829T_1", "COLO829BL_2", "COLO829T_2",
                              "COLO829BL_3", "COLO829T_3", "COLO829BL_4", "COLO829T_4",
                              "COLO829BL_5", "COLO829T_5", "COLO829BL_6", "COLO829T_6",
                              "COLO829BL_7", "COLO829T_7", "COLO829BL_8", "COLO829T_8",
                              "COLO829BL_9", "COLO829T_9", "COLO829BL_10", "COLO829T_10",
                              "COLO829BL_11", "COLO829T_11", "COLO829BL_12", "COLO829T_12",
                              "COLO829BL_13", "COLO829T_13", "COLO829BL_14", "COLO829T_14",
                              "COLO829BL_15", "COLO829T_15", "COLO829BL_16", "COLO829T_16"])

    result = get_properties(data, "file_sets.libraries.analytes.samples.sample_sources.cell_line.code", sort=True)
    assert result == expected_result


def test_get_properties_b():

    data = {
        "donors": [
            {
                "display_title": "DAC_DONOR_COLO829_1"
            },
            {
                "foo": "bar"
            },
            {
                "display_title": "DAC_DONOR_COLO829_2"
            }
        ]
    }

    expected_result = ["DAC_DONOR_COLO829_1", "DAC_DONOR_COLO829_2"]

    result = get_properties(data, "donors.display_title", sort=True)
    assert result == expected_result

    result = get_properties(data, "xyzzy.display_title", sort=True)
    assert result == []


def test_group_items_by_a():

    TESTS_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

    file = os.path.join(TESTS_DATA_DIR, "files_for_dictionary_utils_group_items_for_testing.json")
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
        "item_count": 20,
        "unique_item_count": 10,
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
        "item_count": 11,
        "unique_item_count": 10,
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
        "unique_item_count": 10,
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
        "item_count": 20,
        "unique_item_count": 10,
        "group_count": 9,
        "group_items": {
            "COLO829BL": {
                "group": "donors.display_title",
                "item_count": 4,
                "unique_item_count": 3,
                "group_count": 2,
                "group_items": {
                    "DAC_DONOR_COLO829": {
                        "group": "release_tracker_description",
                        "item_count": 3,
                        "unique_item_count": 3,
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
                        "unique_item_count": 1,
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
                "unique_item_count": 3,
                "group_count": 1,
                "group_items": {
                    "DAC_DONOR_COLO829": {
                        "group": "release_tracker_description",
                        "item_count": 3,
                        "unique_item_count": 3,
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
            "HG002": {
                "group": "donors.display_title",
                "item_count": 2,
                "unique_item_count": 2,
                "group_count": 1,
                "group_items": {
                    None: {
                        "group": "release_tracker_description",
                        "item_count": 2,
                        "unique_item_count": 2,
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
                "unique_item_count": 2,
                "group_count": 1,
                "group_items": {
                    None: {
                        "group": "release_tracker_description",
                        "item_count": 2,
                        "unique_item_count": 2,
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
                "unique_item_count": 2,
                "group_count": 1,
                "group_items": {
                    None: {
                        "group": "release_tracker_description",
                        "item_count": 2,
                        "unique_item_count": 2,
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
                "unique_item_count": 2,
                "group_count": 1,
                "group_items": {
                    None: {
                        "group": "release_tracker_description",
                        "item_count": 2,
                        "unique_item_count": 2,
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
                "unique_item_count": 2,
                "group_count": 1,
                "group_items": {
                    None: {
                        "group": "release_tracker_description",
                        "item_count": 2,
                        "unique_item_count": 2,
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
                "unique_item_count": 2,
                "group_count": 1,
                "group_items": {
                    None: {
                        "group": "release_tracker_description",
                        "item_count": 2,
                        "unique_item_count": 2,
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
            None: {
                "group": "donors.display_title",
                "item_count": 2,
                "unique_item_count": 2,
                "group_count": 2,
                "group_items": {
                    "ST003": {
                        "group": "release_tracker_description",
                        "item_count": 1,
                        "unique_item_count": 1,
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
                        "unique_item_count": 1,
                        "group_count": 1,
                        "group_items": {
                            "WGS Illumina NovaSeq X bam": [
                                "c53931bc-e3dc-4a37-97f3-05ffa2dc438b"
                            ]
                        }
                    }
                }
            }
        }
    }
    assert result == expected_result
    assert compare_dictionaries_ordered(result, expected_result)
