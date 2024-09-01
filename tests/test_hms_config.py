from hms_utils.hms_config import Config


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
            "B": {
                "B1": "${A1}",
                "B2": "b2value_${A1}",
                "B3": "b3value_${A2}"
            }
        }
    })
    assert config.lookup("A/B/B3") == "b3value_123_456_b2value_123"
    # This one is even trickier; want to get A2 from A/B context like test_hmsconfig_b
    # but then notice that is has unexpanded macros, i.e. 123_456_${B2}, and
    # then evaluate the macros within the context of A/A.
    assert config.lookup("A/B/A2") == "123_456_b2value_123"

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
