import os
import pytest
from unittest.mock import patch
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


def test_hms_config_rewrite_e():

    config = Config({
        "foursight": {
            "SSH_TUNNEL_ES_NAME": "SOMEPREFIX-${SSH_TUNNEL_ES_ENV}-SOMEPORT",
            "SSH_TUNNEL_ES_ENV": "${AWS_PROFILE}",
            "smaht": {
                "prod": {
                    "AWS_PROFILE": "smaht-prod",
                    "SSH_TUNNEL_ES_ENV": "smaht-green"
                }
            }
        }
    })
    assert config.lookup("foursight/smaht/prod/SSH_TUNNEL_ES_NAME") == "SOMEPREFIX-smaht-green-SOMEPORT"


def test_hms_config_rewrite_f():
    config = Config({
        "auth0": {
            "local": {
                "secret": "REDACTED_auth0_local_secret_value"
            }
        },
        "foursight": {
            "smaht": {
                "Auth0Secret": "${auth0/local/secret}",
                "XAuth0Secret": "${auth0/local/xsecret}"
            }
        }
    })
    assert config.lookup("foursight/smaht/Auth0Secret") == "REDACTED_auth0_local_secret_value"
    assert config.lookup("foursight/smaht/XAuth0Secret") == "${auth0/local/xsecret}"


def test_hms_config_rewrite_g():

    config = Config({
        "abc": {
            "def": "${auth0/secret}"
        },
        "auth0": {
            "main": "4dn",
            "secret": "some_secret_${main}_${auth0/main}",
        }
    })
    # TODO: Do not like that fact that auth0/main is not found
    # for ${main} within auth0/secret - it is not because the
    # the context is abc/def ... need multiple contexts maybe
    if Config._TRICKY_FIX:
        assert config.lookup("/abc/def") == "some_secret_4dn_4dn"
    else:
        assert config.lookup("/abc/def") == "some_secret_${main}_4dn"


def test_hms_config_rewrite_h():

    config = Config({
        "auth0": {
            "env": "4dn",
            "client": "some_auth0_client_${env}",
        },
        "target": "${auth0/client}"
    })
    assert config.lookup("target") == "some_auth0_client_4dn"

    config = Config({
        "auth0": {
            "env": "4dn",
            "client": "some_auth0_client_${env}",
        },
        "target": {
            "env": "smaht",
            "client": "${auth0/client}"
        }
    })
    assert config.lookup("target/client") == "some_auth0_client_smaht"


def test_hms_config_rewrite_i():

    config = Config({
        "abc": {
            "def": "${auth0/secret}"
        },
        "auth0": {
            "secret": "some_secret_${def}_${main}_${def}",
        },
        "def": "asdf"
    }, exception=True)
    with pytest.raises(Exception):  # circular
        config.lookup("/abc/def")

    config = Config({
        "abc": {
            "def": "${abc}"
        }
    }, exception=True)
    with pytest.raises(Exception):  # primitive type - TODO (should be circular)
        config.lookup("/abc/def")

    config = Config({
        "abc": {
            "def": "${auth0/secret}"
        },
        "auth0": {
            "secret": "some_secret_${def}",
        }
    }, exception=True)
    with pytest.raises(Exception):  # circular
        config.lookup("abc/def")

    config = Config({
        "abc": "${auth0/secret}",
        "auth0": {
            "secret": "some_secret_${abc}",
        }
    }, exception=True)
    with pytest.raises(Exception):  # circular
        config.lookup("abc")


def test_hms_config_rewrite_tricky_a():

    config = Config({
        "abc": {
            "main": "smaht",
            "def": "${auth0/secret}",
        },
        "auth0": {
            "main": "4dn",
            "secret": "iamsecret_${main}",
        }
    })
    assert config.lookup("abc/def") == "iamsecret_smaht"

    config = Config({
        "abc": {
            "main": "smaht",
            "def": "${/auth0/secret}",  # not root
        },
        "auth0": {
            "main": "4dn",
            "secret": "iamsecret_${main}",
        }
    })
    assert config.lookup("abc/def") == "iamsecret_4dn"

    config = Config({
        "abc": {
            "def": "${auth0/secret}"
        },
        "auth0": {
            "main": "4dn",
            "secret": "iamsecret_${main}",
        }
    })
    # TODO: the auth0/secret lookup is in the abc/def context so does not find auth0/main
    # from auth0/secret value; would much rather abc/def give iamsecret_4dn but tricky.
    if Config._TRICKY_FIX:
        assert config.lookup("abc/def") == "iamsecret_4dn"
    else:
        assert config.lookup("abc/def") == "iamsecret_${main}"

    config = Config({
        "abc": {
            "def": "${/auth0/secret}"
        },
        "auth0": {
            "main": "4dn",
            "secret": "iamsecret_${main}",
        }
    })
    # However here the /auth0/secret (with leading slash) look is in the auth0 context
    # so does not find auth0/main from auth0/secret value.
    assert config.lookup("abc/def") == "iamsecret_4dn"


def test_hms_config_rewrite_tricky_b():

    config = Config({
        "alfa": "alfa_value_${charlie/bravo_sub}",
        "alfa2": "alfa_value_${charlie/bravo_sub2}",
        "outer_env": "4dn",
        "env": "cgap",
        "bravo": {
            "charlie": {
                "env": "smaht",
                "bravo_sub": "bravo_sub_value_${env}_${outer_env}_${delta/delta_sub}",
                "bravo_sub2": "bravo_sub_value_${/env}_${outer_env}_${delta/delta_sub}"
            },
            "delta": {
                "delta_sub": "delta_sub_value"
            }
        },
    })
    assert config.lookup("/bravo/alfa") == "alfa_value_bravo_sub_value_smaht_4dn_delta_sub_value"
    assert config.lookup("/bravo/alfa2") == "alfa_value_bravo_sub_value_cgap_4dn_delta_sub_value"

    config = Config({
        "foo": "foo_value_${goo}",
        "goo": "123",
        "bravo": {
            "charlie": {
                "bravo_sub": "bravo_sub_value_${/foo}_${delta}",
            },
            "delta": "delta_value"
        },
    })
    assert config.lookup("/bravo/charlie/bravo_sub") == "bravo_sub_value_foo_value_123_delta_value"


# ----------------------------------------------------------------------------------------------------------------------
# ADAPTED FROM test_hms_config.py ...
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


def test_hms_config_b():
    config = Config({
        "A": {
            "A1": "123",
            "B": {
                "B1": "${A1}"
            }
        }
    })

    assert config.lookup("A/A1") == "123"
    assert config.lookup("A/B/B1") == "123"
    # This was the tricky-ish one; look back up the tree from the A/B context.
    assert config.lookup("A/B/A1") == "123"


def test_hms_config_c():
    config = Config({
        "A": {
            "A1": "123",
            "A2": "${A1}_456_${B2}",
            "A3": "${A1}_789_${B4}",
            "B": {
                "B1": "${A1}",
                "B2": "b2value_${A1}",
                "B3": "b3value_${A2}",
                "B4": "b4value_${B1}"
            }
        }
    })
    assert config.lookup("A/B/B3") == "b3value_123_456_b2value_123"
    # This one is even trickier; want to get A2 from A/B context like the above (test_hms_config_b)
    # test but then here notice that it has unexpanded macros, i.e. ${B2} within 123_456_${B2},
    # and then we want to evaluate the macros within the context of A/B.
    assert config.lookup("A/B/A2") == "123_456_b2value_123"
    assert config.lookup("A/B/A3") == "123_789_b4value_123"

    config = Config({
        "A": {
            "A1": "123",
            "A2": "${A1}_456_${B2}",
            "X": {
               "B": {
                   "B1": "${A1}",
                   "B2": "b2value_${A1}",
                   "B3": "b3value_${A2}"
               }
            }
        }
    })
    assert config.lookup("A/X/B/B3") == "b3value_123_456_b2value_123"

    config = Config({
        "A": {
            "A1": "123",
            "A2": "${A1}_456_${C2}",
            "A3": "${A1}_978_${C3}",
            "B": {
                "C": {
                    "C1": "${A1}",
                    "C2": "b2value_${A1}",
                    "C3": "b3value_${A2}"
                }
            }
        }
    })
    assert config.lookup("A/B/C/C3") == "b3value_123_456_b2value_123"
    assert config.lookup("A/B/C/A1") == "123"
    assert config.lookup("A/B/A1") == "123"
    assert config.lookup("A/A1") == "123"
    assert config.lookup("A1") is None
    assert config.lookup("A") == config.json["A"]
    assert config.lookup("B") is None
    assert config.lookup("A/B/C/A2") == "123_456_b2value_123"
    assert config.lookup("A/B/A2") == "123_456_${C2}"
    assert config.lookup("A/A2") == "123_456_${C2}"
    assert config.lookup("A2") is None
    assert config.lookup("A/B/C/A3") == "123_978_b3value_123_456_b2value_123"


def test_hms_config_d():
    config = Config({
        "foursight": {
            "SSH_TUNNEL_ES_NAME_PREFIX": "ssh_tunnel_elasticsearch_proxy",
            "SSH_TUNNEL_ES_NAME": "${SSH_TUNNEL_ES_NAME_PREFIX}_${SSH_TUNNEL_ES_ENV}_${SSH_TUNNEL_ES_PORT}",  # noqa
            "ES_HOST_LOCAL": "http://localhost:${SSH_TUNNEL_ES_PORT}",
            "smaht": {
                "wolf": {
                    "SSH_TUNNEL_ES_PORT": 9209,
                    "SSH_TUNNEL_ES_ENV": "smaht_wolf",
                    "SSH_TUNNEL_ES_NAME": "${foursight/SSH_TUNNEL_ES_NAME}"
                }
            }
        }
    })
    assert config.lookup("foursight/smaht/wolf/ES_HOST_LOCAL") == "http://localhost:9209"


def test_hms_config_e():
    config = Config({
        "foursight": {
            "SSH_TUNNEL_ES_NAME_PREFIX": "ssh_tunnel_elasticsearch_proxy",
            "SSH_TUNNEL_ES_NAME": "${SSH_TUNNEL_ES_NAME_PREFIX}_${SSH_TUNNEL_ES_ENV}_${SSH_TUNNEL_ES_PORT}",  # noqa
            "ES_HOST_LOCAL": "http://localhost:${SSH_TUNNEL_ES_PORT}",
            "smaht": {
                "wolf": {
                    "ES_HOST_LOCAL": "http://localhost:${SSH_TUNNEL_ES_PORT}x",
                    "SSH_TUNNEL_ES_PORT": 9209,
                    "SSH_TUNNEL_ES_ENV": "smaht_wolf",
                    "SSH_TUNNEL_ES_NAME": "${foursight/SSH_TUNNEL_ES_NAME}"
                }
            }
        }
    })
    assert config.lookup("foursight/smaht/wolf/ES_HOST_LOCAL") == "http://localhost:9209x"


def test_hms_config_f():
    config = Config({
        "foursight": {
            "SSH_TUNNEL_ES_NAME_PREFIX": "ssh-tunnel-es-proxy",
            "SSH_TUNNEL_ES_NAME": "${SSH_TUNNEL_ES_NAME_PREFIX}-${SSH_TUNNEL_ES_ENV}-${SSH_TUNNEL_ES_PORT}",
            "SSH_TUNNEL_ES_ENV": "${AWS_PROFILE}",
            "ES_HOST_LOCAL": "http://localhost:${SSH_TUNNEL_ES_PORT}",
            "4dn": {
                "AWS_PROFILE": "4dn",
                "SSH_TUNNEL_ES_ENV": "${AWS_PROFILE}-mastertest",
                "SSH_TUNNEL_ES_PORT": "9201",
                "dev": {
                    "IDENTITY": "FoursightDevelopmentLocalApplicationSecret",
                },
                "prod": {
                    "IDENTITY": "FoursightProductionApplicationConfiguration",
                }
            },
            "cgap": {
                "wolf": {
                    "AWS_PROFILE": "cgap-wolf",
                    "SSH_TUNNEL_ES_ENV": "${AWS_PROFILE}",
                    "SSH_TUNNEL_ES_PORT": 9203
                }
            },
            "smaht": {
                "wolf": {
                    "AWS_PROFILE": "smaht-wolf",
                    "SSH_TUNNEL_ES_PORT": 9209
                }
            }
        }
    })

    # These were the tricky ones.
    assert config.lookup("foursight/smaht/wolf/SSH_TUNNEL_ES_NAME") == "ssh-tunnel-es-proxy-smaht-wolf-9209"
    assert config.lookup("foursight/cgap/wolf/SSH_TUNNEL_ES_NAME") == "ssh-tunnel-es-proxy-cgap-wolf-9203"
    assert config.lookup("foursight/4dn/prod/SSH_TUNNEL_ES_NAME") == "ssh-tunnel-es-proxy-4dn-mastertest-9201"

    assert config.lookup("foursight/4dn/AWS_PROFILE") == "4dn"
    assert config.lookup("foursight/4dn/dev/AWS_PROFILE") == "4dn"
    assert config.lookup("foursight/4dn/SSH_TUNNEL_ES_ENV") == "4dn-mastertest"
    assert config.lookup("foursight/4dn/dev/SSH_TUNNEL_ES_ENV") == "4dn-mastertest"
    assert config.lookup("foursight/4dn/SSH_TUNNEL_ES_PORT") == "9201"
    assert config.lookup("foursight/4dn/dev/SSH_TUNNEL_ES_PORT") == "9201"

    assert config.lookup("foursight/smaht/wolf/ES_HOST_LOCAL") == "http://localhost:9209"


def test_hms_config_g():

    config_file = os.path.join(TESTS_DATA_DIR, "config_a.json")
    secrets_file = os.path.join(TESTS_DATA_DIR, "secrets_but_not_really_a.json")
    config = Config(config_file)
    secrets = Config(secrets_file)
    config.merge(secrets.json)

    value = config.lookup("foursight/smaht/wolf/SSH_TUNNEL_ELASTICSEARCH_NAME")
    assert value == "ssh-tunnel-elasticsearch-proxy-smaht-wolf-9209"

    value = config.lookup("foursight/smaht/prod/SSH_TUNNEL_ELASTICSEARCH_NAME")
    assert value == "ssh-tunnel-elasticsearch-proxy-smaht-green-9208"

    value = config.lookup("foursight/smaht/Auth0Secret")
    assert value == "REDACTED_auth0_local_secret_value"

    value = config.lookup("foursight/smaht/Auth0Client")
    assert value == "UfM_REDACTED_Hf9"

    return  # TODO

    mocked_aws_secrets_value = {
        "deploying_iam_user": "kent.pitman.biotest",
        "ENCODED_AUTH0_CLIENT": "XYZ_REDACTED_auth0_client_ABC",
        "ENCODED_AUTH0_SECRET": "XYZ_REDACTED_auth0_secret_ABC",
        "RDS_NAME": "rds-cgap-wolf"
    }
    hms_config_class = "hms_utils.hms_config_rewriting.ConfigWithAwsMacroExpander"
    with patch(f"{hms_config_class}._aws_get_secret_value") as mocked_aws_get_secret_value:
        mocked_aws_get_secret_value.return_value = mocked_aws_secrets_value
        value = config.lookup("foursight/cgap/wolf/Auth0Secret")
        assert value == "XYZ_REDACTED_auth0_secret_ABC"

    with patch(f"{hms_config_class}._aws_get_secret_value") as mocked_aws_get_secret_value:
        mocked_aws_get_secret_value.return_value = mocked_aws_secrets_value
        value = config.lookup("auth0/prod/secret", aws_secret_context_path="foursight/cgap/wolf/")
        assert value == "XYZ_REDACTED_auth0_secret_ABC"
