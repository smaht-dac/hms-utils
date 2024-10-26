from __future__ import annotations
import sys
from typing import Any, Callable, List, Optional, Type, Union
from uuid import uuid4 as uuid
from hms_utils.type_utils import to_float, to_integer, to_non_empty_string_list


class Argv:

    BOOLEAN = 0x0001
    FLOAT = 0x0002
    FLOATS = 0x0004
    INTEGER = 0x0008
    INTEGERS = 0x0010
    STRING = 0x0020
    STRINGS = 0x0040
    DEFAULT = 0x0080
    DEFAULTS = 0x0100
    OPTIONAL = 0x0200
    REQUIRED = 0x0400

    _ESCAPE_VALUE = "--"
    _FUZZY_OPTION_PREFIX = "-"
    _FUZZY_OPTION_PREFIX_LEN = len(_FUZZY_OPTION_PREFIX)
    _OPTION_PREFIX = "--"
    _OPTION_PREFIX_LEN = len(_OPTION_PREFIX)

    class _Arg(str):

        def __new__(cls, value: str, argv: Argv) -> None:
            null = value is None
            value = (value.strip() if argv._strip else value) if isinstance(value, str) else ""
            value = super().__new__(cls, value)
            value._argv = argv
            value._null = null
            return value

        @property
        def is_option(self) -> bool:
            # return self._argv._is_option(self, fuzzy=self._argv._fuzzy)
            return self._argv._is_option(self)

        @property
        def is_null(self) -> bool:
            return self._null

        @property
        def is_not_null(self) -> bool:
            return not self._null

        def is_any_of(self, options) -> bool:
            def match(option: str) -> bool:
                nonlocal self
                if self._argv._escaping:
                    return False
                if isinstance(option, str) and (option := option.strip()):
                    if ((self == option) or (self._argv._fuzzy and option.startswith(Argv._OPTION_PREFIX) and
                                             (self == Argv._FUZZY_OPTION_PREFIX + option[Argv._OPTION_PREFIX_LEN:]))):
                        return True
                return False
            return any(match(option) for option in options)

        def set_value_boolean(self, option: Argv._Option) -> bool:
            if isinstance(option, str): option = Argv._Option(option)  # noqa
            if self.is_any_of(option._options) and (property_name := option._property_name):
                setattr(self._argv._values, property_name, True)
                return True
            return False

        def set_value_string(self, option: Argv._Option) -> bool:
            return self._set_value_property(option)

        def set_value_strings(self, option: Argv._Option) -> bool:
            return self._set_value_property_multiple(option)

        def set_value_integer(self, option: Argv._Option) -> bool:
            return self._set_value_property(option, convert=to_integer)

        def set_value_integers(self, option: Argv._Option) -> bool:
            return self._set_value_property_multiple(option, convert=to_integer)

        def set_value_float(self, option: Argv._Option) -> bool:
            return self._set_value_property(option, convert=to_float)

        def set_value_floats(self, option: Argv._Option) -> bool:
            return self._set_value_property_multiple(option, convert=to_float)

        def set_default_value_string(self, option: Argv._Option) -> bool:
            return self._set_default_value_property(option)

        def set_default_value_strings(self, option: Argv._Option) -> bool:
            return self._set_default_value_properties(option)

        def set_default_value_integer(self, option: Argv._Option) -> bool:
            return self._set_default_value_property(option, convert=to_integer)

        def set_default_value_integers(self, option: Argv._Option) -> bool:
            return self._set_default_value_properties(option, convert=to_integer)

        def set_default_value_float(self, option: Argv._Option) -> bool:
            return self._set_default_value_property(option, convert=to_float)

        def set_default_value_floats(self, option: Argv._Option) -> bool:
            return self._set_default_value_properties(option, convert=to_float)

        def _set_value_property(self, option: Argv._Option, convert: Optional[Callable] = None) -> bool:
            if isinstance(option, str): option = Argv._Option(option)  # noqa
            if ((property_name := option._property_name) and
                self.is_any_of(option._options) and (not hasattr(self._argv._values, property_name))):  # noqa
                if (peek := self._argv._peek).is_not_null and (not peek.is_option):
                    if (not callable(convert)) or ((peek := convert(peek)) is not None):
                        setattr(self._argv._values, property_name, peek if callable(convert) else str(peek))
                        self._argv._next
                        return True
            return False

        def _set_value_property_multiple(self, option: Union[Argv._Option, str],
                                         convert: Optional[Callable] = None) -> bool:
            if isinstance(option, str): option = Argv._Option(option)  # noqa
            if not callable(convert):
                convert = lambda value: str(value)  # noqa
            if self.is_any_of(option._options):
                if property_name := option._property_name:
                    property_values = []
                    if (hasattr(self._argv._values, property_name) and
                        (property_value := getattr(self._argv._values, property_name))):  # noqa
                        if isinstance(property_value, list):
                            property_values[:0] = property_value
                        elif (property_value := convert(property_value)) is not None:
                            property_values.append(property_value)
                    setattr(self._argv._values, property_name, property_values)
                    while True:
                        if ((peek := self._argv._peek).is_null or peek.is_option or ((peek := convert(peek)) is None)):
                            break
                        property_values.append(peek)
                        self._argv._next
                    return True
            return False

        def _set_default_value_property(self, option: Argv._Option, convert: Optional[Callable] = None) -> bool:
            if self and (not self.is_option):
                property_value = self
                for option in option._options:
                    if (not callable(convert)) or ((property_value := convert(property_value)) is not None):
                        if not hasattr(self._argv._values, option):
                            setattr(self._argv._values, option, property_value)
                            return True
            return False

        def _set_default_value_properties(self, option: Argv._Option, convert: Optional[Callable] = None) -> bool:
            parsed = False ; peek = self  # noqa
            for option in option._options:
                option_values = getattr(self._argv._values, option) if hasattr(self._argv._values, option) else None
                while True:
                    if ((peek is None) or peek.is_null or peek.is_option or
                        (callable(convert) and ((peek := convert(peek)) is None))):  # noqa
                        break
                    if option_values is None:
                        option_values = []
                        setattr(self._argv._values, option, option_values)
                    option_values.append(peek if callable(convert) else str(peek))
                    parsed = True
                    if (peek := self._argv._peek).is_null or peek.is_option:
                        break
                    self._argv._next
            return parsed

    class _Values:
        pass

    class _OptionDefinitions:
        def __init__(self, fuzzy: bool = True) -> None:
            self._definitions = []
            self._fuzzy = fuzzy is not False
            self._rule_oneof = []
            self._option_type_action_map = {
                # 0: Argv._Arg.set_value_string,
                0: Argv._Arg.set_value_boolean,
                Argv.BOOLEAN: Argv._Arg.set_value_boolean,
                Argv.STRING: Argv._Arg.set_value_string,
                Argv.STRINGS: Argv._Arg.set_value_strings,
                Argv.INTEGER: Argv._Arg.set_value_integer,
                Argv.INTEGERS: Argv._Arg.set_value_integers,
                Argv.FLOAT: Argv._Arg.set_value_float,
                Argv.FLOATS: Argv._Arg.set_value_floats
            }
            self._default_option_type_action_map = {
                0: Argv._Arg.set_default_value_string,
                Argv.STRING: Argv._Arg.set_default_value_string,
                Argv.STRINGS: Argv._Arg.set_default_value_string,
                Argv.INTEGER: Argv._Arg.set_default_value_integer,
                Argv.INTEGERS: Argv._Arg.set_default_value_integer,
                Argv.FLOAT: Argv._Arg.set_default_value_float,
                Argv.FLOATS: Argv._Arg.set_default_value_float
            }
            self._defaults_option_type_action_map = {
                0: Argv._Arg.set_default_value_strings,
                Argv.STRING: Argv._Arg.set_default_value_strings,
                Argv.STRINGS: Argv._Arg.set_default_value_strings,
                Argv.INTEGER: Argv._Arg.set_default_value_integers,
                Argv.INTEGERS: Argv._Arg.set_default_value_integers,
                Argv.FLOAT: Argv._Arg.set_default_value_floats,
                Argv.FLOATS: Argv._Arg.set_default_value_floats
            }

        def define_option(self, option_type: int, options: List[str]) -> None:
            if isinstance(option_type, int) and isinstance(options, list):
                option_required = (option_type & Argv.REQUIRED) == Argv.REQUIRED
                if (option_type & Argv.DEFAULT) == Argv.DEFAULT:
                    option_type_action_map = self._default_option_type_action_map
                elif (option_type & Argv.DEFAULTS) == Argv.DEFAULTS:
                    option_type_action_map = self._defaults_option_type_action_map
                else:
                    option_type_action_map = self._option_type_action_map
                option_type &= ~(Argv.REQUIRED | Argv.OPTIONAL | Argv.DEFAULT | Argv.DEFAULTS)
                if action := option_type_action_map.get(option_type):
                    self._definitions.append(Argv._Option(
                        options=options, required=option_required, action=action, fuzzy=self._fuzzy))

        def add_rule_oneof(self, options: List[str]) -> None:
            if options := list(set(to_non_empty_string_list(options))):
                self._rule_oneof.append(options)

    class _Option:
        def __init__(self,
                     options: Optional[List[str]] = None,
                     required: bool = False,
                     action: Optional[Callable] = None,
                     fuzzy: bool = True) -> None:
            self._options = to_non_empty_string_list(options)
            self._required = required is True
            self._fuzzy = fuzzy is not True
            self._action = action if callable(action) else lambda: None

        @property
        def _option_name(self) -> str:
            return self._options[0] if self._options else ""

        @property
        def _property_name(self) -> str:
            if self._options and (option := self._options[0]):
                if option.startswith(Argv._OPTION_PREFIX):
                    option = option[Argv._OPTION_PREFIX_LEN:]
                elif self._fuzzy and option.startswith(Argv._FUZZY_OPTION_PREFIX):
                    option = option[Argv._FUZZY_OPTION_PREFIX_LEN:]
                return option.replace("-", "_")
            return ""

    def __init__(self, *args, argv: Optional[List[str]] = None,
                 parse: bool = False, exit: bool = False, fuzzy: bool = True,
                 strip: bool = True, skip: bool = True, escape: bool = True, delete: bool = False) -> None:
        self._argi = 0
        self._fuzzy = fuzzy is not False
        self._strip = strip is not False  # TODO: make strip = False by default
        self._escape = escape is not False
        self._escaping = False
        self._delete = delete is True
        self._values = Argv._Values()
        self._exit = exit is True
        if (len(args) == 1) and isinstance(args[0], list):
            # Here, the given args are the actual command-line arguments to process/parse.
            if not (isinstance(argv, list) and argv):
                argv = args[0]
            self._option_definitions = self._process_option_definitions()
        else:
            # Here, the given args should be the definitions for processing/parsing command-line args.
            self._option_definitions = self._process_option_definitions(*args)
        self._argv = argv if isinstance(argv, list) and argv else (sys.argv[1:] if skip is not False else sys.argv)
        if parse is True:
            self.parse()

    @property
    def list(self) -> List[str]:
        return self._argv

    @property
    def values(self) -> Argv._Values:
        return self._values

    def parse(self, *args, skip: bool = True, report: bool = True,
              exit: Optional[bool] = None, printf: Optional[Callable] = None) -> None:

        if exit not in (True, False):
            exit = self._exit
        if ((len(args) == 1) and isinstance(args[0], list)) or (len(args) == 0):
            # Here, the given args are the actual command-line arguments to process/parse;
            # and this Argv object already should have the definitions for processing/parsing these.
            if not self._option_definitions:
                return None, None
            self._argv = args[0] if (len(args) > 0) else (sys.argv[1:] if (skip is not False) else sys.argv)
        else:
            # Here, the given args are the definitions for processing/parsing command-line args;
            # and this Argv object already as the actual command-line arguments to process/parse.
            self._option_definitions = self._process_option_definitions(*args)  # xyzzy

        missing_options = []
        unparsed_args = []
        oneof_rule_violations_toomany = []
        oneof_rule_violations_missing = []

        if self._option_definitions:
            for arg in self:
                parsed = False
                for option in self._option_definitions._definitions:
                    if option._action(arg, option):
                        parsed = True
                        break
                if not parsed:
                    unparsed_args.append(arg)
            for rule in self._option_definitions._rule_oneof:
                oneof_args = []
                for oneof in rule:
                    if (option := self._find_option_definition(oneof)) and (property_name := option._property_name):
                        if hasattr(self._values, property_name):
                            oneof_args.append(option._option_name)
                if (not oneof_args) and option:
                    # oneof_rule_violations_missing.append(rule)
                    pass
                elif len(oneof_args) > 1:
                    oneof_rule_violations_toomany.append(oneof_args)
            for option in self._option_definitions._definitions:
                if not hasattr(self._values, property_name := option._property_name):
                    if option._required:
                        missing_options.append(option._option_name)
                    setattr(self._values, property_name, None)
            if report is not False:
                if not callable(printf):
                    printf = lambda *args, **kwargs: print(*args, **kwargs, file=sys.stderr)  # noqa
                errors = False
                if unparsed_args:
                    printf(f"Unrecognized argument"
                           f"{'s' if len(unparsed_args) > 1 else ''}: {', '.join(unparsed_args)}")
                    errors = True
                if missing_options:
                    printf(f"Missing required option"
                           f"{'s' if len(missing_options) > 1 else ''}: {', '.join(missing_options)}")
                    errors = True
                for oneof_rule_violation in oneof_rule_violations_toomany:
                    printf(f"Options may not be specified together: {', '.join(oneof_rule_violation)}")
                    errors = True
                for oneof_rule_violation in oneof_rule_violations_missing:
                    printf(f"One of these options must be specified: {', '.join(oneof_rule_violation)}")
                    errors = True
                if errors and (exit is True):
                    sys.exit(1)

        return missing_options, unparsed_args

    def _process_option_definitions(self, *args) -> None:

        def flatten(*args):
            flattened_args = []
            def flatten(*args):  # noqa
                nonlocal flattened_args
                for arg in args:
                    if isinstance(arg, (list, tuple)):
                        for itemi in range(len(arg)):
                            if isinstance(item := arg[itemi], int) and ((itemi + 1) < len(arg)):
                                if isinstance(next_item := arg[itemi + 1], tuple) or isinstance(next_item, str):
                                    if (item & Argv.OPTIONAL) != Argv.OPTIONAL:
                                        item |= Argv.REQUIRED
                            flatten(item)
                    else:
                        flattened_args.append(arg)
            flatten(args)
            return flattened_args

        option_definitions = Argv._OptionDefinitions(fuzzy=self._fuzzy)

        if (len(args) == 1) and isinstance(options := args[0], dict):
            args = []
            for option_type in options:
                option_options = options[option_type]
                if isinstance(option_type, str):
                    if (index := option_type.find("_")) > 1:
                        if (option_type := option_type[0:index]) == "oneof":
                            option_definitions.add_rule_oneof(option_options)
                            continue
                        option_type = to_integer(option_type[0:index])
                if Argv._is_option_type(option_type) and (option_options := to_non_empty_string_list(option_options)):
                    if not any(self._is_option(option) for option in option_options):
                        if default_is_but_should_not_be_boolean := ((option_type & Argv.BOOLEAN) == Argv.BOOLEAN):
                            option_type &= ~Argv.BOOLEAN
                        if option_type & (Argv.STRINGS | Argv.INTEGERS | Argv.INTEGERS | Argv.DEFAULTS):
                            option_type |= Argv.DEFAULTS
                            if default_is_but_should_not_be_boolean:
                                option_type | ~Argv.STRING
                        else:
                            option_type |= Argv.DEFAULT
                            if default_is_but_should_not_be_boolean:
                                option_type | ~Argv.STRINGS
                    args.append(option_type)
                    args.append(option_options)
                else:
                    pass

        if args := flatten(args):
            option_type = None ; options = [] ; parsing_options = None  # noqa
            for arg in args:
                if Argv._is_option_type(arg):
                    if (parsing_options is True) and option_type and options:
                        option_definitions.define_option(option_type, options)
                        option_type = None ; options = []  # noqa
                    parsing_options = False
                    option_type = arg
                elif isinstance(arg, str) and (arg := arg.strip()):
                    if (parsing_options is False) and option_type and options:
                        option_definitions.define_option(option_type, options)
                        option_type = None ; options = []  # noqa
                    parsing_options = True
                    options.append(arg)
            if options:
                option_definitions.define_option(option_type or Argv.BOOLEAN, options)
        return option_definitions

    def _find_option_definition(self, option: str) -> Optional[Argv._Option]:
        if isinstance(option, str) and option:
            for option_definition in self._option_definitions._definitions:
                if option in option_definition._options:
                    return option_definition
        return None

    @property
    def _peek(self) -> Optional[str]:
        return Argv._Arg(self._argv[self._argi], self) if self._argi < len(self._argv) else Argv._Arg(None, self)

    @property
    def _next(self) -> Optional[str]:
        if (value := self._peek) is not None:
            if self._delete:
                del self._argv[0]
            else:
                self._argi += 1
            return value
        return None

    def __iter__(self) -> Argv:
        return self

    def __next__(self) -> Optional[str]:
        if self._argi >= len(self._argv):
            raise StopIteration
        arg = self._argv[self._argi]
        if self._delete:
            del self._argv[0]
        else:
            self._argi += 1
        if (arg == Argv._ESCAPE_VALUE) and self._escape and (not self._escaping):
            self._escaping = True
            return self.__next__()
        return Argv._Arg(arg, self)

    def _is_option(self, value: str) -> bool:
        if isinstance(value, str) and (value := value.strip()):
            if value.startswith(Argv._OPTION_PREFIX) and (value := value[Argv._OPTION_PREFIX_LEN:].strip()):
                return True
            elif self._fuzzy:
                if value.startswith(Argv._FUZZY_OPTION_PREFIX) and value[Argv._FUZZY_OPTION_PREFIX_LEN:].strip():
                    return True
        return False

    @staticmethod
    def _is_option_type(option_type: Any) -> bool:
        if isinstance(option_type, int):
            return (((Argv.BOOLEAN | Argv.DEFAULT | Argv.DEFAULTS |
                      Argv.FLOAT | Argv.FLOATS | Argv.INTEGER | Argv.INTEGERS |
                      Argv.STRING | Argv.STRINGS | Argv.OPTIONAL | Argv.REQUIRED) & option_type) == option_type)
        return False

    def __getattr__(self, name: str):
        if not hasattr(self._values, name):
            raise AttributeError(f"Property for argument not found: {name}")
        return getattr(self._values, name)


class ARGV(Argv):

    @staticmethod
    def OPTIONAL(type: Optional[Type[Union[str, int, float, bool]]] = None, _required: bool = False) -> str:
        if isinstance(type, list) and (len(type) == 1):
            type = type[0]
            if type == str: option_type = Argv.STRINGS  # noqa
            elif type == int: option_type = Argv.INTEGERS  # noqa
            elif type == float: option_type = Argv.FLOATS  # noqa
            elif type == bool: option_type = Argv.BOOLEAN  # noqa
            else: option_type = Argv.BOOLEAN  # noqa
        else:
            if type == str: option_type = Argv.STRING  # noqa
            elif type == int: option_type = Argv.INTEGER  # noqa
            elif type == float: option_type = Argv.FLOAT  # noqa
            elif type == bool: option_type = Argv.BOOLEAN  # noqa
            else: option_type = Argv.BOOLEAN  # noqa
        if _required is True:
            option_type |= Argv.REQUIRED
        else:
            option_type |= Argv.OPTIONAL
        return str(option_type) + "_" + str(uuid())

    @staticmethod
    def REQUIRED(type: Optional[Type[Union[str, int, float, bool]]] = None):
        return ARGV.OPTIONAL(type=type, _required=True)

    @classmethod
    @property
    def ONE_OF(cls):
        return f"oneof_{str(uuid()).replace('-', '_')}"


# args = Argv({"foo": "bar"})
# argv = Argv()
# x = argv.foo


if True:
    args = ["abc", "def", "--config", "file.json", "--verbose",
            "-debug", "--configs", "ghi.json", "jkl.json", "mno.json"]
    argv = Argv(args, delete=True)
    argv.parse(
        "--config", "-file", Argv.STRING,
        "--configs", Argv.STRINGS,
        "--verbose", Argv.BOOLEAN,
        "--debug", Argv.BOOLEAN
    )
#   argv.parse(
#       Argv.STRING, "--config", "-file",
#       Argv.STRINGS, "--configs",
#       Argv.BOOLEAN, "--verbose",
#       Argv.BOOLEAN, "--debug"
#   )
    argv.parse(
        Argv.STRING, ("--config", "-file"),
        Argv.STRINGS, ["--configs", "--configs"],
        Argv.BOOLEAN, "--verbose",
        Argv.BOOLEAN, "--debug"
    )
    assert argv.values.verbose is True
    assert argv.values.debug is True
    assert argv.values.config == "file.json"
    assert argv.values.configs == ["ghi.json", "jkl.json", "mno.json"]


if True:
    # args = Argv(
    #     [Argv.STRINGS, "--config", "--conf"],
    #     [Argv.STRING, "--config", "--conf"],
    #     [Argv.INTEGERS, "--count"],
    #     [Argv.FLOATS, "--key"]
    # )
    args = Argv(
        Argv.STRINGS, "--config", "--conf",
        Argv.STRING, "--config", "--conf",
        Argv.INTEGERS, "--count",
        Argv.FLOATS, "--key",
        Argv.STRING, "--foo",
        Argv.STRING, "goo",
        Argv.STRING, "--import-file",
        Argv.DEFAULT, "others",
    )
    missing, unparsed = args.parse(["--config", "abc", "ghi", "-xyz",
                                    "--config", "foo", "--import-file", "secrets.json",
                                    "-count", "123", "456", "-key", "321", "2342.234",
                                    "-124", "somefile.json", "some-other"])

    assert args.config == ["abc", "ghi", "foo"]
    assert args.count == [123, 456]
    assert args.import_file == "secrets.json"
    assert args.key == [321, 2342.234]
    assert args.others == "somefile.json", "some-other"
    assert unparsed == ["-xyz", "-124", "some-other"]  # TODO: why goo

if True:
    argv = Argv(
        # Argv.DEFAULT, "files",
        Argv.INTEGER, ["--max", "--maximum"],
        Argv.FLOAT, ["--pi", "--pie"],
        Argv.STRINGS, ("--config", "--conf"),
        Argv.STRINGS, ["--secrets", "--secret"],
        Argv.STRINGS, ("--merge"),
        Argv.STRINGS, ["--includes", "--include", "--imports", "--import",
                       "--import-config", "--import-configs", "--import-conf"],
        Argv.STRINGS, ["--include-secrets", "--include-secret", "--import-secrets", "--import-secret"],
        Argv.BOOLEAN, ["--list"],
        Argv.BOOLEAN, ["--tree"],
        Argv.BOOLEAN, ["--dump"],
        Argv.BOOLEAN, ["--json"],
        Argv.BOOLEAN, ("--formatted", "--format"),
        Argv.BOOLEAN, ["--jsonf"],
        Argv.BOOLEAN, ["--raw"],
        Argv.BOOLEAN, ["--verbose"],
        Argv.BOOLEAN, ["--debug"],
        Argv.STRINGS, ("--shell", "-shell", "--script", "-script", "--scripts", "-scripts", "--command", "-command",
                       "--commands", "-commands", "--function", "-function", "--functions", "-functions"),
        Argv.STRING, ("--password", "--passwd"),
        Argv.STRING, ["--exports", "--export"],
        Argv.STRING, ["--exports-file", "--export-file"],
        Argv.DEFAULT, "thedefault", "thedefault2",
        Argv.DEFAULTS, "thedefaults",
        Argv.DEFAULT | Argv.OPTIONAL, "thedefaultb",
        Argv.DEFAULTS | Argv.OPTIONAL, "thedefaultfoo",
        #    Argv.DEFAULTS, "thedefaults"
    )
    missing, unparsed = argv.parse(["foo", "bara", "barb", "-xyz", "goo",
                                    "-passwd", "pas", "--shell", "hoo", "-config", "configfile",
                                    "--max", "124", "--pie", "3.141562"])
    assert argv.password == "pas"
    assert argv.max == 124
    assert argv.pi == 3.141562

    assert argv.values.thedefault == "foo"
    assert argv.values.thedefault2 == "bara"
    assert argv.values.thedefaults == ["barb", "goo"]
    assert argv.values.thedefaultb is None
    assert argv.values.thedefaultfoo is None

    print("MISSING:")
    print(missing)
    print("UNPARSED:")
    print(unparsed)
    print(argv.values.config)

if True:
    argv = Argv(
        Argv.DEFAULTS | Argv.FLOAT, "floats", "reals"
    )
    x, y = argv.parse(["12", "34", "56", "1.2", "3.4"])
    print(x)
    print(y)
    assert argv.floats == [12, 34, 56, 1.2, 3.4]

if True:
    argv = Argv(
        Argv.DEFAULT | Argv.INTEGER, "max",
        Argv.DEFAULTS | Argv.FLOAT, "floats", "reals"
    )
    x, y = argv.parse(["12", "34", "56", "1.2", "3.4"])
    print(x)
    print(y)
    assert argv.max == 12
    assert argv.floats == [34, 56, 1.2, 3.4]


if True:
    argv = Argv(
        Argv.STRING, ("--password", "--passwd")
    )
    missing, unparsed = argv.parse(["foo", "bara", "barb", "-xyz", "goo", "-passwd", "pas"])
    assert argv.password == "pas"

if True:
    argv = Argv(
        Argv.STRING, ["--password"],
        Argv.DEFAULTS, "file"
    )
    missing, unparsed = argv.parse(["foo", "--password", "pas"])
    assert argv.password == "pas"

if True:
    argv = Argv(
        Argv.STRING, ["--password"],
        Argv.DEFAULTS, ("thedefaults"), strip=False)
    missing, unparsed = argv.parse(["foo", "bar", "--password", "pas", " argwithspace ", "", ""])
    assert argv.password == "pas"
    assert argv.thedefaults == ["foo", "bar", " argwithspace ", "", ""]

if True:
    argv = Argv({
        Argv.STRING: ["--password"],
        Argv.DEFAULTS: "thedefaults",
    })
    missing, unparsed = argv.parse(["foo", "bar", "--password", "pas", " argwithspace ", "", ""])
    assert argv.password == "pas"
    assert argv.thedefaults == ["foo", "bar", "argwithspace", "", ""]

if True:
    argv = Argv({
        Argv.STRING: ["--password"],
        Argv.REQUIRED: "--req",
        Argv.DEFAULTS: "thedefaults",
    })
    missing, unparsed = argv.parse(["foo", "bar", "--password", "pas", " argwithspace ", "", "", "--req", "xyz"])
    assert argv.password == "pas"
    assert argv.thedefaults == ["foo", "bar", "argwithspace", "", "", "xyz"]
    assert argv.req is True


if True:
    argv = ARGV({
        ARGV.OPTIONAL(str): ("--password"),
        ARGV.OPTIONAL(str): ("--xpassword"),
        ARGV.REQUIRED(bool): ["--req", "--reqx"],
        ARGV.REQUIRED([str]): "thedefaults",
        ARGV.REQUIRED(float): "--maxn",
    })
    missing, unparsed = argv.parse(["foo", "bar", "-password", "pas", " argwithspace ", "", "", "-reqx", "xyz"])
    assert argv.password == "pas"
    print(argv.thedefaults)
    assert argv.thedefaults == ["foo", "bar", "argwithspace", "", "", "xyz"]
    assert argv.req is True
    assert argv.values.xpassword is None
    assert unparsed == []
    assert missing == ["--maxn"]


if True:
    argv = ARGV({
        ARGV.OPTIONAL(str): ["--encrypt"],
        ARGV.OPTIONAL(str): ["--decrypt"],
        ARGV.OPTIONAL(str): ["--output", "--out"],
        ARGV.OPTIONAL(bool): ["--yes", "--force"],
        ARGV.OPTIONAL(bool): ["--verbose"],
        ARGV.OPTIONAL(bool): ["--debug"],
        ARGV.OPTIONAL(str): ["--password", "--passwd"],
        # ARGV.ONE_OF: ["--encrypt", "--decrypt"]
    })
    missing, unparsed = argv.parse(["--encrypt", "somefile", "--encrypt", "anotherfile"], report=False)
    assert missing == []
    assert unparsed == ["--encrypt", "anotherfile"]
    assert argv.encrypt == "somefile"
    assert argv.decrypt is None
