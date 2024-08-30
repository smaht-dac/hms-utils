from hms_utils.hmsconfig import Config


def test_hmsconfig():
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
                "juliet": "5_${alpha}_${zulu}_${charlie.echo}"
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
    assert config.lookup("charlie.echo") == "3_1_2_4_echooooo99"
    assert config.lookup("charlie.zulu.xx") == "zuluhere"
