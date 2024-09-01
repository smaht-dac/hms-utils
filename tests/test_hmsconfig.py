from hms_utils.hms_config import Config


def test_hmsconfig_a():
    config = {
        "alpha": "1",
        "bravo": "${alpha}_2",
        "charlie": {
            "echo": "3_${bravo}_4_echooooo${zulu}",
            "foxtrot": "4",
            "zulu": {
                "xx": "zuluhere"
            },
            "indigo": {
                "juliet": "5_${alpha}_${zulu}_${charlie/echo}"
            }
        },
        "delta": {
            "golf": "3",
            "hotel": "3"
        },
        "zulu": "99"
    }
    expected = {
        "alpha": "1",
        "bravo": "1_2",
        "charlie": {
            "echo": "3_1_2_4_echooooo99",
            "foxtrot": "4",
            "zulu": {
                "xx": "zuluhere"
            },
            "indigo": {
                "juliet": "5_1_99_3_1_2_4_echooooo99"
            }
        },
        "delta": {
            "golf": "3",
            "hotel": "3"
        },
        "zulu": "99"
    }
    config = Config(config)
    assert config.json == expected
    assert config.lookup("zulu") == "99"
    assert config.lookup("charlie/echo") == "3_1_2_4_echooooo99"
    assert config.lookup("charlie/zulu/xx") == "zuluhere"

def test_hmsconfig_b():
    config = {
        "A": {
            "A1": "123",
            "B": {
                "B1": "${A1}"
            }
        }
    }
    expected = {
        "A": {
            "A1": "123",
            "B": {
                "B1": "123"
            }
        }
    }
    config = Config(config)
    #assert config.json == expected
    import pdb ; pdb.set_trace()  # noqa
    x = config.json
    assert config.lookup("A/A1") == "123"
    assert config.lookup("A/B/B1") == "123"
    import pdb ; pdb.set_trace()  # noqa
    assert config.lookup("A/B/A1") == "123"
