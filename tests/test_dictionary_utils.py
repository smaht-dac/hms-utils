from hms_utils.dictionary_utils import get_properties


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
