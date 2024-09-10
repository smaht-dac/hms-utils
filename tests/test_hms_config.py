import os
from hms_utils.hms_config import Config

TESTS_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def test_hmsconfig_a():
    config = Config({
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
    })
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
    assert config.json == expected
    assert config.lookup("zulu") == "99"
    assert config.lookup("charlie/echo") == "3_1_2_4_echooooo99"
    assert config.lookup("charlie/zulu/xx") == "zuluhere"


def test_hmsconfig_b():
    config = Config({
        "A": {
            "A1": "123",
            "B": {
                "B1": "${A1}"
            }
        }
    })
    expected = {
        "A": {
            "A1": "123",
            "B": {
                "B1": "123"
            }
        }
    }
    assert config.json == expected
    assert config.lookup("A/A1") == "123"
    assert config.lookup("A/B/B1") == "123"
    # This was the tricky-ish one; look back up the tree from the A/B context.
    assert config.lookup("A/B/A1") == "123"


def test_hmsconfig_c():
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
    # This one is even trickier; want to get A2 from A/B context like the above (test_hmsconfig_b)
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


def test_hmsconfig_d():
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


def test_hmsconfig_e():
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


def test_hmsconfig_f():
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


def test_hmsconfig_g():

    config_file = os.path.join(TESTS_DATA_DIR, "config_a.json")
    secrets_file = os.path.join(TESTS_DATA_DIR, "secrets_a.json")
    config = Config(config_file)
    secrets = Config(secrets_file)
    merged_config = config.merge_secrets(secrets)

    value = merged_config.lookup("foursight/smaht/wolf/SSH_TUNNEL_ELASTICSEARCH_NAME")
    assert value == "ssh-tunnel-elasticsearch-proxy-smaht-wolf-9209"

    value = merged_config.lookup("foursight/smaht/prod/SSH_TUNNEL_ELASTICSEARCH_NAME")
    assert value == "ssh-tunnel-elasticsearch-proxy-smaht-green-9208"

    value = merged_config.lookup("foursight/smaht/Auth0Secret")
    assert value == "REDACTED_auth0_local_secret_value"

    value = merged_config.lookup("foursight/smaht/Auth0Client")
    assert value == "UfM_REDACTED_Hf9"

    return  # TODO

    value = merged_config.lookup("foursight/smaht/wolf/SSH_TUNNEL_ELASTICSEARCH_NAME")
    assert value == ""

    value = config.lookup("foursight/smaht/prod/SSH_TUNNEL_ELASTICSEARCH_NAME")
    assert value == ""

    value = config.lookup("foursight/4dn/dev/SSH_TUNNEL_ELASTICSEARCH_NAME")
    assert value == ""
