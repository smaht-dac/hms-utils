from contextlib import contextmanager
import os
import pytest
from unittest.mock import patch
from hms_utils.config.config import Config
from hms_utils.config.config_with_secrets import ConfigWithSecrets
from hms_utils.config.config_with_aws_macros import ConfigWithAwsMacros

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
    assert config.lookup("/bravo/alfa", inherit_none=True) is None
    assert config.lookup("/bravo/alfa", inherit_simple=True) == "alfa_value"


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

    inherit_simple = False
    assert config.lookup("/bravo/bravo_sub_two", inherit_simple=inherit_simple) == "bravo_sub_two_value"
    assert config.lookup("/bravo/echo", inherit_simple=inherit_simple) == "echo_value"
    assert config.lookup("/bravo/alfa", inherit_simple=inherit_simple) == "alfa_value"
    assert config.lookup("/bravo/delta/echo", inherit_simple=inherit_simple) == "delta_echo_value"
    assert config.lookup("/delta/echo", inherit_simple=inherit_simple) == "delta_echo_value"
    assert config.lookup("/delta/alfa", inherit_simple=inherit_simple) == "alfa_value"
    assert config.lookup("/delta/bravo/bravo_sub_three/bravo_sub_sub", inherit_simple=inherit_simple) == {
            "bravo_sub_sub_sub": "bravo_sub_sub_sub_value",
            "bravo_sub_sub_sub_two": "bravo_sub_sub_sub_two_value__alfa_value"}

    inherit_simple = True
    assert config.lookup("/bravo/bravo_sub_two", inherit_simple=inherit_simple) == "bravo_sub_two_value"
    assert config.lookup("/bravo/echo", inherit_simple=inherit_simple) == "echo_value"
    assert config.lookup("/bravo/alfa", inherit_simple=inherit_simple) == "alfa_value"
    assert config.lookup("/bravo/delta/echo", inherit_simple=inherit_simple) is None
    assert config.lookup("/delta/bravo/bravo_sub_three/bravo_sub_sub", inherit_simple=inherit_simple) is None

    assert config.path(config.json['bravo']['bravo_sub_three']) == "/bravo/bravo_sub_three"


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
    }, raise_exception=True)
    with pytest.raises(Exception):  # circular
        config.lookup("/abc/def")

    config = Config({
        "abc": {
            "def": "${abc}"
        }
    }, raise_exception=True)
    with pytest.raises(Exception):  # primitive type - TODO (should be circular)
        config.lookup("/abc/def")

    config = Config({
        "abc": {
            "def": "${auth0/secret}"
        },
        "auth0": {
            "secret": "some_secret_${def}",
        }
    }, raise_exception=True)
    with pytest.raises(Exception):  # circular
        config.lookup("abc/def")

    config = Config({
        "abc": "${auth0/secret}",
        "auth0": {
            "secret": "some_secret_${abc}",
        }
    }, raise_exception=True)
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


def test_hms_config_rewrite_secrets_c():
    config = Config({
        "bbb": {
            "AWS_PROFILE": "${foo}",
            "foo": "smaht-wolf",
            "secret": "${aws-secret:C4AppConfigSmahtWolf/ENCODED_AUTH0_CLIENT}"
        }
    }, secrets=True)
    with mock_aws_secret("C4AppConfigSmahtWolf", "ENCODED_AUTH0_CLIENT", "some_secret_value_0123456789"):
        assert config.evaluate(show=None) == {
            "bbb": {
                "AWS_PROFILE": (f"{ConfigWithSecrets._SECRET_VALUE_START}{ConfigWithSecrets._TYPE_NAME_STR}:"
                                f"smaht-wolf{ConfigWithSecrets._SECRET_VALUE_END}"),
                "foo": (f"{ConfigWithSecrets._SECRET_VALUE_START}{ConfigWithSecrets._TYPE_NAME_STR}:"
                        f"smaht-wolf{ConfigWithSecrets._SECRET_VALUE_END}"),
                "secret": (f"{ConfigWithSecrets._SECRET_VALUE_START}{ConfigWithAwsMacros._TYPE_NAME_AWS}:123456789:"
                           f"C4AppConfigSmahtWolf:ENCODED_AUTH0_CLIENT:some_secret_value_0123456789"
                           f"{ConfigWithSecrets._SECRET_VALUE_END}")
            }
        }
        assert config.evaluate(show=True) == {
            "bbb": {
                "AWS_PROFILE": "smaht-wolf",
                "foo": "smaht-wolf",
                "secret": "some_secret_value_0123456789"
            }
        }
        assert config.evaluate(show=False) == {
            "bbb": {
                "AWS_PROFILE": ConfigWithSecrets._SECRET_OBFUSCATED_VALUE,
                "foo": ConfigWithSecrets._SECRET_OBFUSCATED_VALUE,
                "secret": ConfigWithSecrets._SECRET_OBFUSCATED_VALUE
            }
        }
        assert config.lookup("/bbb/secret", show=True) == "some_secret_value_0123456789"
        assert config.lookup("/bbb/secret", show=False) == "********"
        assert config.lookup("/bbb/secret", show=None) == (
            f"{ConfigWithSecrets._SECRET_VALUE_START}"
            f"{ConfigWithAwsMacros._TYPE_NAME_AWS}:123456789:"
            f"C4AppConfigSmahtWolf:ENCODED_AUTH0_CLIENT:"
            f"some_secret_value_0123456789{ConfigWithSecrets._SECRET_VALUE_END}")


def test_hms_config_rewrite_secrets_a():

    config_file = os.path.join(TESTS_DATA_DIR, "config_a.json")
    secrets_file = os.path.join(TESTS_DATA_DIR, "secrets_but_not_really_a.json")
    config = Config(config_file)
    secrets = Config(secrets_file)
    config.merge(secrets)

    assert config.data(show=None) == {'auth0': {'local': {'client': 'UfM_REDACTED_Hf9', 'secret': '@@@@@@@__mark_secret_start__[str:REDACTED_auth0_local_secret_value]__mark_secret_end__@@@@@@@'}, 'prod': {'client': 'DQx_REDACTED_kN1', 'secret': '${aws-secret:ENCODED_AUTH0_SECRET}'}}, 'foursight': {'4dn': {'AWS_PROFILE': '4dn', 'dev': {'IDENTITY': 'FoursightDevelopmentLocalApplicationSecret', 'STACK_NAME': 'c4-foursight-development-stack'}, 'prod': {'IDENTITY': 'FoursightProductionApplicationConfiguration', 'STACK_NAME': 'c4-foursight-fourfront-production-stack'}, 'SSH_TUNNEL_ELASTICSEARCH_ENV': '${AWS_PROFILE}-mastertest', 'SSH_TUNNEL_ELASTICSEARCH_PORT': '9201'}, 'cgap': {'wolf': {'Auth0Secret': '${auth0/prod/secret}', 'AWS_PROFILE': 'cgap-wolf', 'IDENTITY': 'C4DatastoreCgapWolfC4DatastorecgapwolfapplicationconfigurationApplicationConfiguration', 'SSH_TUNNEL_ELASTICSEARCH_PORT': 9203, 'STACK_NAME': 'c4-foursight-cgap-wolf-stack'}}, 'CHALICE_LOCAL': True, 'ES_HOST_LOCAL': 'http://localhost:${SSH_TUNNEL_ELASTICSEARCH_PORT}', 'REDIS_HOST_LOCAL': 'redis://localhost:6379', 'smaht': {'Auth0Client': '${auth0/local/client}', 'Auth0Secret': '${auth0/local/secret}', 'prod': {'AWS_PROFILE': 'smaht-prod', 'IDENTITY': 'C4AppConfigFoursightSmahtProduction', 'SSH_TUNNEL_ELASTICSEARCH_ENV': 'smaht-green', 'SSH_TUNNEL_ELASTICSEARCH_PORT': 9208, 'STACK_NAME': 'c4-foursight-production-stack'}, 'wolf': {'AWS_PROFILE': 'smaht-wolf', 'IDENTITY': 'C4AppConfigFoursightSmahtDevelopment', 'SSH_TUNNEL_ELASTICSEARCH_PORT': 9209, 'STACK_NAME': 'c4-foursight-development-stack'}}, 'SSH_TUNNEL_ELASTICSEARCH_ENV': '${AWS_PROFILE}', 'SSH_TUNNEL_ELASTICSEARCH_NAME': '${SSH_TUNNEL_ELASTICSEARCH_NAME_PREFIX}-${SSH_TUNNEL_ELASTICSEARCH_ENV}-${SSH_TUNNEL_ELASTICSEARCH_PORT}', 'SSH_TUNNEL_ELASTICSEARCH_NAME_PREFIX': 'ssh-tunnel-elasticsearch-proxy'}, 'portal': {'cgap': {'devtest': {'Auth0Client': '${auth0/local/client}', 'AWS_PROFILE': 'cgap-devtest', 'GLOBAL_BUCKET_ENV': 'cgap-devtest-main-foursight-envs', 'GLOBAL_ENV_BUCKET': 'cgap-devtest-main-foursight-envs', 'S3_ENCRYPT_KEY': '${s3/prod/encrypt-key}'}}, 'fourfront': {'mastertest': {'Auth0Client': '${auth0/local/client}', 'Auth0Secret': '${auth0/local/secret}', 'AWS_PROFILE': '4dn', 'GLOBAL_ENV_BUCKET': 'foursight-prod-envs', 'IDENTITY': 'FoursightDevelopmentLocalApplicationSecret', 'S3_ENCRYPT_KEY': '${s3/4dn-mastertest/encrypt-key}'}}, 'smaht': {'GOOGLE_API_KEY': '@@@@@@@__mark_secret_start__[str:REDACTED_E]__mark_secret_end__@@@@@@@', 'SUBMITR_METADATA_TEMPLATE_SHEET_ID': '@@@@@@@__mark_secret_start__[str:REDACTED_F]__mark_secret_end__@@@@@@@', 'wolf': {'Auth0Client': '${auth0/local/client}', 'Auth0Secret': '${auth0/local/secret}', 'AWS_PROFILE': 'smaht-wolf', 'IDENTITY': 'C4AppConfigSmahtWolf', 'S3_ENCRYPT_KEY_ID': 'REDACTED-ABC-DEF-GHI-JKL', 'tests': {'IDENTITY': 'C4AppConfigSmahtDevtest'}}}}, 's3': {'4dn-mastertest': {'encrypt-key': '@@@@@@@__mark_secret_start__[str:REDACTED_D]__mark_secret_end__@@@@@@@'}, 'prod': {'encrypt-key': '@@@@@@@__mark_secret_start__[str:REDACTED_C]__mark_secret_end__@@@@@@@'}}, 'zzzbool': '@@@@@@@__mark_secret_start__[bool:False]__mark_secret_end__@@@@@@@', 'zzzfloat': '@@@@@@@__mark_secret_start__[float:1.23]__mark_secret_end__@@@@@@@', 'zzzint': '@@@@@@@__mark_secret_start__[int:345]__mark_secret_end__@@@@@@@', 'zzzstructured': [12345, 2, [99, 88], 3, {'xyzzynested': '@@@@@@@__mark_secret_start__[str:xyzzynestedvalue]__mark_secret_end__@@@@@@@', 'xyzzynesttwo': '@@@@@@@__mark_secret_start__[str:sdfasfasdfas]__mark_secret_end__@@@@@@@', 'arry': [5, 6, {'fooy': '@@@@@@@__mark_secret_start__[str:fooabc]__mark_secret_end__@@@@@@@'}, 7]}]}  # noqa TODO

    assert config.data(show=True) == {'auth0': {'local': {'client': 'UfM_REDACTED_Hf9', 'secret': 'REDACTED_auth0_local_secret_value'}, 'prod': {'client': 'DQx_REDACTED_kN1', 'secret': '${aws-secret:ENCODED_AUTH0_SECRET}'}}, 'foursight': {'4dn': {'AWS_PROFILE': '4dn', 'dev': {'IDENTITY': 'FoursightDevelopmentLocalApplicationSecret', 'STACK_NAME': 'c4-foursight-development-stack'}, 'prod': {'IDENTITY': 'FoursightProductionApplicationConfiguration', 'STACK_NAME': 'c4-foursight-fourfront-production-stack'}, 'SSH_TUNNEL_ELASTICSEARCH_ENV': '${AWS_PROFILE}-mastertest', 'SSH_TUNNEL_ELASTICSEARCH_PORT': '9201'}, 'cgap': {'wolf': {'Auth0Secret': '${auth0/prod/secret}', 'AWS_PROFILE': 'cgap-wolf', 'IDENTITY': 'C4DatastoreCgapWolfC4DatastorecgapwolfapplicationconfigurationApplicationConfiguration', 'SSH_TUNNEL_ELASTICSEARCH_PORT': 9203, 'STACK_NAME': 'c4-foursight-cgap-wolf-stack'}}, 'CHALICE_LOCAL': True, 'ES_HOST_LOCAL': 'http://localhost:${SSH_TUNNEL_ELASTICSEARCH_PORT}', 'REDIS_HOST_LOCAL': 'redis://localhost:6379', 'smaht': {'Auth0Client': '${auth0/local/client}', 'Auth0Secret': '${auth0/local/secret}', 'prod': {'AWS_PROFILE': 'smaht-prod', 'IDENTITY': 'C4AppConfigFoursightSmahtProduction', 'SSH_TUNNEL_ELASTICSEARCH_ENV': 'smaht-green', 'SSH_TUNNEL_ELASTICSEARCH_PORT': 9208, 'STACK_NAME': 'c4-foursight-production-stack'}, 'wolf': {'AWS_PROFILE': 'smaht-wolf', 'IDENTITY': 'C4AppConfigFoursightSmahtDevelopment', 'SSH_TUNNEL_ELASTICSEARCH_PORT': 9209, 'STACK_NAME': 'c4-foursight-development-stack'}}, 'SSH_TUNNEL_ELASTICSEARCH_ENV': '${AWS_PROFILE}', 'SSH_TUNNEL_ELASTICSEARCH_NAME': '${SSH_TUNNEL_ELASTICSEARCH_NAME_PREFIX}-${SSH_TUNNEL_ELASTICSEARCH_ENV}-${SSH_TUNNEL_ELASTICSEARCH_PORT}', 'SSH_TUNNEL_ELASTICSEARCH_NAME_PREFIX': 'ssh-tunnel-elasticsearch-proxy'}, 'portal': {'cgap': {'devtest': {'Auth0Client': '${auth0/local/client}', 'AWS_PROFILE': 'cgap-devtest', 'GLOBAL_BUCKET_ENV': 'cgap-devtest-main-foursight-envs', 'GLOBAL_ENV_BUCKET': 'cgap-devtest-main-foursight-envs', 'S3_ENCRYPT_KEY': '${s3/prod/encrypt-key}'}}, 'fourfront': {'mastertest': {'Auth0Client': '${auth0/local/client}', 'Auth0Secret': '${auth0/local/secret}', 'AWS_PROFILE': '4dn', 'GLOBAL_ENV_BUCKET': 'foursight-prod-envs', 'IDENTITY': 'FoursightDevelopmentLocalApplicationSecret', 'S3_ENCRYPT_KEY': '${s3/4dn-mastertest/encrypt-key}'}}, 'smaht': {'GOOGLE_API_KEY': 'REDACTED_E', 'SUBMITR_METADATA_TEMPLATE_SHEET_ID': 'REDACTED_F', 'wolf': {'Auth0Client': '${auth0/local/client}', 'Auth0Secret': '${auth0/local/secret}', 'AWS_PROFILE': 'smaht-wolf', 'IDENTITY': 'C4AppConfigSmahtWolf', 'S3_ENCRYPT_KEY_ID': 'REDACTED-ABC-DEF-GHI-JKL', 'tests': {'IDENTITY': 'C4AppConfigSmahtDevtest'}}}}, 's3': {'4dn-mastertest': {'encrypt-key': 'REDACTED_D'}, 'prod': {'encrypt-key': 'REDACTED_C'}}, 'zzzbool': False, 'zzzfloat': 1.23, 'zzzint': 345, 'zzzstructured': [12345, 2, [99, 88], 3, {'xyzzynested': 'xyzzynestedvalue', 'xyzzynesttwo': 'sdfasfasdfas', 'arry': [5, 6, {'fooy': 'fooabc'}, 7]}]}  # noqa TODO

    assert config.data(show=False) == {'auth0': {'local': {'client': 'UfM_REDACTED_Hf9', 'secret': '********'}, 'prod': {'client': 'DQx_REDACTED_kN1', 'secret': '${aws-secret:ENCODED_AUTH0_SECRET}'}}, 'foursight': {'4dn': {'AWS_PROFILE': '4dn', 'dev': {'IDENTITY': 'FoursightDevelopmentLocalApplicationSecret', 'STACK_NAME': 'c4-foursight-development-stack'}, 'prod': {'IDENTITY': 'FoursightProductionApplicationConfiguration', 'STACK_NAME': 'c4-foursight-fourfront-production-stack'}, 'SSH_TUNNEL_ELASTICSEARCH_ENV': '${AWS_PROFILE}-mastertest', 'SSH_TUNNEL_ELASTICSEARCH_PORT': '9201'}, 'cgap': {'wolf': {'Auth0Secret': '${auth0/prod/secret}', 'AWS_PROFILE': 'cgap-wolf', 'IDENTITY': 'C4DatastoreCgapWolfC4DatastorecgapwolfapplicationconfigurationApplicationConfiguration', 'SSH_TUNNEL_ELASTICSEARCH_PORT': 9203, 'STACK_NAME': 'c4-foursight-cgap-wolf-stack'}}, 'CHALICE_LOCAL': True, 'ES_HOST_LOCAL': 'http://localhost:${SSH_TUNNEL_ELASTICSEARCH_PORT}', 'REDIS_HOST_LOCAL': 'redis://localhost:6379', 'smaht': {'Auth0Client': '${auth0/local/client}', 'Auth0Secret': '${auth0/local/secret}', 'prod': {'AWS_PROFILE': 'smaht-prod', 'IDENTITY': 'C4AppConfigFoursightSmahtProduction', 'SSH_TUNNEL_ELASTICSEARCH_ENV': 'smaht-green', 'SSH_TUNNEL_ELASTICSEARCH_PORT': 9208, 'STACK_NAME': 'c4-foursight-production-stack'}, 'wolf': {'AWS_PROFILE': 'smaht-wolf', 'IDENTITY': 'C4AppConfigFoursightSmahtDevelopment', 'SSH_TUNNEL_ELASTICSEARCH_PORT': 9209, 'STACK_NAME': 'c4-foursight-development-stack'}}, 'SSH_TUNNEL_ELASTICSEARCH_ENV': '${AWS_PROFILE}', 'SSH_TUNNEL_ELASTICSEARCH_NAME': '${SSH_TUNNEL_ELASTICSEARCH_NAME_PREFIX}-${SSH_TUNNEL_ELASTICSEARCH_ENV}-${SSH_TUNNEL_ELASTICSEARCH_PORT}', 'SSH_TUNNEL_ELASTICSEARCH_NAME_PREFIX': 'ssh-tunnel-elasticsearch-proxy'}, 'portal': {'cgap': {'devtest': {'Auth0Client': '${auth0/local/client}', 'AWS_PROFILE': 'cgap-devtest', 'GLOBAL_BUCKET_ENV': 'cgap-devtest-main-foursight-envs', 'GLOBAL_ENV_BUCKET': 'cgap-devtest-main-foursight-envs', 'S3_ENCRYPT_KEY': '${s3/prod/encrypt-key}'}}, 'fourfront': {'mastertest': {'Auth0Client': '${auth0/local/client}', 'Auth0Secret': '${auth0/local/secret}', 'AWS_PROFILE': '4dn', 'GLOBAL_ENV_BUCKET': 'foursight-prod-envs', 'IDENTITY': 'FoursightDevelopmentLocalApplicationSecret', 'S3_ENCRYPT_KEY': '${s3/4dn-mastertest/encrypt-key}'}}, 'smaht': {'GOOGLE_API_KEY': '********', 'SUBMITR_METADATA_TEMPLATE_SHEET_ID': '********', 'wolf': {'Auth0Client': '${auth0/local/client}', 'Auth0Secret': '${auth0/local/secret}', 'AWS_PROFILE': 'smaht-wolf', 'IDENTITY': 'C4AppConfigSmahtWolf', 'S3_ENCRYPT_KEY_ID': 'REDACTED-ABC-DEF-GHI-JKL', 'tests': {'IDENTITY': 'C4AppConfigSmahtDevtest'}}}}, 's3': {'4dn-mastertest': {'encrypt-key': '********'}, 'prod': {'encrypt-key': '********'}}, 'zzzbool': '********', 'zzzfloat': '********', 'zzzint': '********', 'zzzstructured': [12345, 2, [99, 88], 3, {'xyzzynested': '********', 'xyzzynesttwo': '********', 'arry': [5, 6, {'fooy': '********'}, 7]}]}  # noqa TODO


def test_hms_config_rewrite_secrets_b():

    secrets = Config({
        "aaa": {
            "ccc": "cccvalue"  # ,
            # "ddd": "${aws-secret:C4AppConfigSmahtWolf/ENCODED_AUTH0_CLIENT}"
        }
    }, secrets=True)

    assert secrets.lookup("/aaa", show=True) == {"ccc": "cccvalue"}
    assert secrets.lookup("/aaa", show=False) == {"ccc": "********"}
    assert secrets.lookup("/", show=None) == {"aaa": {"ccc": "@@@@@@@__mark_secret_start__[str:cccvalue]__mark_secret_end__@@@@@@@"}}  # noqa
    assert secrets.lookup("/", show=True) == {"aaa": {"ccc": "cccvalue"}}
    assert secrets.lookup("/", show=False) == {"aaa": {"ccc": "********"}}
    assert secrets.lookup("/aaa", show=None) == {"ccc": "@@@@@@@__mark_secret_start__[str:cccvalue]__mark_secret_end__@@@@@@@"}  # noqa


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
    })

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
    config.merge(secrets)

    value = config.lookup("foursight/smaht/wolf/SSH_TUNNEL_ELASTICSEARCH_NAME")
    assert value == "ssh-tunnel-elasticsearch-proxy-smaht-wolf-9209"

    value = config.lookup("foursight/smaht/prod/SSH_TUNNEL_ELASTICSEARCH_NAME")
    assert value == "ssh-tunnel-elasticsearch-proxy-smaht-green-9208"

    value = config.lookup("foursight/smaht/Auth0Secret", show=True)
    assert value == "REDACTED_auth0_local_secret_value"

    value = config.lookup("foursight/smaht/Auth0Secret")
    assert value == Config._SECRET_OBFUSCATED_VALUE

    value = config.lookup("foursight/smaht/Auth0Secret", show=False)
    assert value == Config._SECRET_OBFUSCATED_VALUE

    value = config.lookup("foursight/smaht/Auth0Secret", show=None)
    assert value == f"{Config._SECRET_VALUE_START}str:REDACTED_auth0_local_secret_value{Config._SECRET_VALUE_END}"

    value = config.lookup("foursight/smaht/Auth0Client")
    assert value == "UfM_REDACTED_Hf9"

    def mock_aws_get_secret(config, secrets_name, secret_name, aws_profile):  # noqa
        value = config.lookup("auth0/prod/secret")
        assert value == "${aws-secret:ENCODED_AUTH0_SECRET}"
        assert secrets_name == "C4DatastoreCgapWolfC4DatastorecgapwolfapplicationconfigurationApplicationConfiguration"
        assert secret_name == "ENCODED_AUTH0_SECRET"
        return "mocked_aws_secret_value_1234567890"
    hms_config_with_aws_secrets_class_name = "hms_utils.config.config_with_aws_macros.ConfigWithAwsMacros"
    hms_config_with_aws_secrets_get_secrets_function_name = f"{hms_config_with_aws_secrets_class_name}._aws_get_secret"
    with patch(hms_config_with_aws_secrets_get_secrets_function_name, new=mock_aws_get_secret):
        value = config.lookup("foursight/cgap/wolf/Auth0Secret")
        assert value == "mocked_aws_secret_value_1234567890"


@contextmanager
def mock_aws_secret(secrets_name, secret_name, secret_value):
    hms_config_with_aws_secrets_class_name = "hms_utils.config.config_with_aws_macros.ConfigWithAwsMacros"
    hms_config_with_aws_secrets_get_secrets_function_name = (
        f"{hms_config_with_aws_secrets_class_name}._aws_get_secret_value")
    def mock_aws_get_secret(config, secrets_name, secret_name, aws_profile=None):  # noqa
        nonlocal secret_value
        return secret_value, "123456789"
    with patch(hms_config_with_aws_secrets_get_secrets_function_name, new=mock_aws_get_secret):
        yield
