import os
from hms_utils.hms_config_rewriting import Config

TESTS_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def test_hms_config_rewrite_a():

    config = Config({
        "alfa": "alfa_value",
        "bravo": {
            "bravo_sub": "bravo_sub_value"
        },
        "delta": "delta_value"
    })

    assert config.unpack_path("/abc/def/ghi") == ["/", "abc", "def", "ghi"]
    assert config.unpack_path("//abc/def/ghi") == ["/", "abc", "def", "ghi"]
    assert config.unpack_path("abc/def/ghi") == ["abc", "def", "ghi"]
    assert config.unpack_path("/abc/../def/ghi") == ["/", "def", "ghi"]
    assert config.unpack_path("abc/../def/ghi") == ["def", "ghi"]
    assert config.unpack_path("/abc/def/../ghi") == ["/", "abc", "ghi"]
    assert config.unpack_path("abc/../../def/ghi") == ["def", "ghi"]
    assert config.unpack_path("/abc/../../def/ghi") == ["/", "def", "ghi"]
    assert config.unpack_path("/abc/def/ghi") == ["/", "abc", "def", "ghi"]

    assert config.normalize_path("/abc/def/ghi") == "/abc/def/ghi"
    assert config.normalize_path("//abc/def/ghi") == "/abc/def/ghi"
    assert config.normalize_path("abc/def/ghi") == "abc/def/ghi"
    assert config.normalize_path("/abc/../def/ghi") == "/def/ghi"
    assert config.normalize_path("abc/../def/ghi") == "def/ghi"
    assert config.normalize_path("/abc/def/../ghi") == "/abc/ghi"
    assert config.normalize_path("abc/../../def/ghi") == "def/ghi"
    assert config.normalize_path("/abc/../../def/ghi") == "/def/ghi"
    assert config.normalize_path("/abc/def/ghi") == "/abc/def/ghi"
    assert config.normalize_path("/abc/./def/./ghi") == "/abc/def/ghi"

    assert config.lookup("alfa") == "alfa_value"
    assert config.lookup("/alfa") == "alfa_value"
    assert config.lookup("//alfa") == "alfa_value"
    assert config.lookup("foo") is None
    assert config.lookup("alfa/foo") is None
    assert config.lookup("/alfa/foo") is None

    assert config.lookup("bravo") == {"bravo_sub": "bravo_sub_value"}
    assert config.lookup("/bravo") == {"bravo_sub": "bravo_sub_value"}
    assert config.lookup("/bravo/foo/..") == {"bravo_sub": "bravo_sub_value"}
    assert config.lookup("/bravo/") == {"bravo_sub": "bravo_sub_value"}
    assert config.lookup("/bravo/.") == {"bravo_sub": "bravo_sub_value"}
    assert config.lookup("/bravo/./") == {"bravo_sub": "bravo_sub_value"}
    assert config.lookup("bravo/bravo_sub") == "bravo_sub_value"
    assert config.lookup("/bravo/bravo_sub") == "bravo_sub_value"
    assert config.lookup("/bravo/alfa") == "alfa_value"
    assert config.lookup("/bravo/alfa", noinherit=True) is None
    assert config.lookup("/bravo/alfa", simple=True) == "alfa_value"


def test_hms_config_rewrite_c():

    config = Config({
        "alfa": "alfa_value",
        "bravo": {
            "bravo_sub": "bravo_sub_value",
            "bravo_sub_two": "bravo_sub_two_value",
            "bravo_sub_three": {
                "bravo_sub_sub": {
                    "bravo_sub_sub_sub": "bravo_sub_sub_sub_value",
                    "bravo_sub_sub_sub_two": "bravo_sub_sub_sub_two_value__${alfa}"
                 }
            }
        },
        "delta": {
            "echo": "delta_echo_value"
        },
        "echo": "echo_value"
    })

    simple = False
    assert config.lookup("/bravo/bravo_sub_two", simple=simple) == "bravo_sub_two_value"
    assert config.lookup("/bravo/echo", simple=simple) == "echo_value"
    assert config.lookup("/bravo/alfa", simple=simple) == "alfa_value"
    assert config.lookup("/bravo/delta/echo", simple=simple) == "delta_echo_value"
    assert config.lookup("/delta/echo", simple=simple) == "delta_echo_value"
    assert config.lookup("/delta/alfa", simple=simple) == "alfa_value"
    assert config.lookup("/delta/bravo/bravo_sub_three/bravo_sub_sub", simple=simple) == {
            "bravo_sub_sub_sub": "bravo_sub_sub_sub_value",
            "bravo_sub_sub_sub_two": "bravo_sub_sub_sub_two_value__alfa_value"}

    simple = True
    assert config.lookup("/bravo/bravo_sub_two", simple=simple) == "bravo_sub_two_value"
    assert config.lookup("/bravo/echo", simple=simple) == "echo_value"
    assert config.lookup("/bravo/alfa", simple=simple) == "alfa_value"
    assert config.lookup("/bravo/delta/echo", simple=simple) is None
    assert config.lookup("/delta/bravo/bravo_sub_three/bravo_sub_sub", simple=simple) is None


def test_hms_config_rewrite_d():

    config = Config({
        "alfa": "${alfa_macro_a}_alpha_inter_${aws_profile}",
        "alfa_macro_a": "alfa_macro_value_a",
        "alfa_macro_b": "alfa_macro_value_b",
        "bravo": {
            "aws_profile": "4dn",
            "bravo_sub": "bravo_sub_value",
            "bravo_sub_with_alfa_macro": "${alfa}_xyzzy",
            "bravo_sub_with_macro": "${alfa_macro_a}_alpha_inter_${alfa_macro_b}",
        },
        "delta": "delta_value"
    })

    assert config.lookup("alfa") == "alfa_macro_value_a_alpha_inter_${aws_profile}"
    assert config.lookup("bravo/bravo_sub_with_macro") == "alfa_macro_value_a_alpha_inter_alfa_macro_value_b"
    # The alfa macro sub-value ${aws_profile} evaluated in context of /bravo.
    assert config.lookup("bravo/bravo_sub_with_alfa_macro") == "alfa_macro_value_a_alpha_inter_4dn_xyzzy"


# ----------------------------------------------------------------------------------------------------------------------
# COPIED FROM test_hms_config.py ...
# ----------------------------------------------------------------------------------------------------------------------

def test_hms_config_a():

    config = Config({
        "alpha": "1",
        "bravo": "${alpha}_2",
        "charlie": {
            "echo": "3_${bravo}_4_echooooo${zulu}",
            "echoxx": "3_${bravo}_4_echooooo${zulu/xx}",
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
    }, warning=True)

    assert config.lookup("zulu") == "99"
    assert config.lookup("charlie/echo") == "3_1_2_4_echooooo${zulu}"  # WARNING: zule evaluates to non-string.
    assert config.lookup("charlie/echoxx") == "3_1_2_4_echooooozuluhere"
    assert config.lookup("charlie/zulu/xx") == "zuluhere"
