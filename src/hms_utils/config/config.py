from typing import Callable, Optional
from hms_utils.config.config_with_secrets import ConfigWithSecrets
from hms_utils.config.config_with_aws_macros import ConfigWithAwsMacros
from hms_utils.dictionary_parented import DictionaryParented as JSON


class Config(ConfigWithSecrets, ConfigWithAwsMacros):

    def __init__(self, config: JSON,
                 name: Optional[str] = None,
                 path_separator: Optional[str] = None,
                 custom_macro_lookup: Optional[Callable] = None,
                 raise_exception: bool = False,
                 secrets: bool = False,
                 noaws: bool = False, **kwargs) -> None:

        super().__init__(config=config,
                         name=name,
                         path_separator=path_separator,
                         custom_macro_lookup=custom_macro_lookup,
                         raise_exception=raise_exception,
                         secrets=secrets,
                         noaws=noaws, **kwargs)

    @staticmethod
    def default():
        config = Config("~/.config/hms/config.json")
        config.merge(Config("~/.config/hms/secrets.json"))
        return config
