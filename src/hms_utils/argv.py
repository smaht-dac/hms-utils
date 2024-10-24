from __future__ import annotations
import sys
from typing import Any, Callable, List, Optional, Union
from hms_utils.type_utils import to_float, to_integer, to_string_list


class Argv:

    BOOLEAN = 0x0001
    DEFAULT = 0x0002
    DEFAULTS = 0x0004
    FLOAT = 0x0008
    FLOATS = 0x0010
    INTEGER = 0x0020
    INTEGERS = 0x0040
    STRING = 0x0080
    STRINGS = 0x0100
    OPTIONAL = 0x1000
    REQUIRED = 0x2000

    _ESCAPE_VALUE = "--"
    _FUZZY_OPTION_PREFIX = "-"
    _FUZZY_OPTION_PREFIX_LENGTH = len(_FUZZY_OPTION_PREFIX)
    _OPTION_PREFIX = "--"
    _OPTION_PREFIX_LENGTH = len(_OPTION_PREFIX)
    _TYPES = [BOOLEAN, DEFAULT, DEFAULTS, FLOAT, FLOATS, INTEGER, INTEGERS, STRING, STRINGS]

    class _Arg(str):

        def __new__(cls, value: str, argv: Argv) -> None:
            value = (value.strip() if argv._strip else value) if isinstance(value, str) else ""
            value = super().__new__(cls, value)
            value._argv = argv
            return value

        @property
        def is_option(self) -> bool:
            return self._argv._is_option(self)

        def is_any_of(self, options) -> bool:
            def match(option: str) -> bool:
                nonlocal self
                if self._argv._escaping:
                    return False
                if isinstance(option, str) and (option := option.strip()):
                    if ((self == option) or
                        (self._argv._fuzzy and option.startswith(Argv._OPTION_PREFIX) and
                         (self == Argv._FUZZY_OPTION_PREFIX + option[Argv._OPTION_PREFIX_LENGTH:]))):
                        return True
                return False
            return any(match(option) for option in options)

        def set_value_boolean(self, option: Argv._Option) -> bool:
            if isinstance(option, str): option = Argv._Option(option)  # noqa xyzzy
            if self.is_any_of(option._options):
                if self._set_value_property(option, property_value=True):
                    return True
            return False

        def set_value_string(self, option: Argv._Option) -> bool:
            if isinstance(option, str): option = Argv._Option(option)  # noqa xyzzy
            if self.is_any_of(option._options):
                if (peek := self._argv._peek) and (not peek.is_option):
                    if self._set_value_property(option, property_value=peek):
                        self._argv._next
                        return True
            return False

        def set_value_strings(self, option: Argv._Option) -> bool:
            return self._set_value_property_multiple(option)

        def set_value_integer(self, option: Argv._Option) -> bool:
            if self.is_any_of(option._options):
                if (peek := to_integer(self._argv._peek)) is not None:
                    if self._set_value_property(option, property_value=peek):
                        self._argv._next
                        return True
            return False

        def set_value_integers(self, option: Argv._Option) -> bool:
            return self._set_value_property_multiple(option, to_type=to_integer)

        def set_value_float(self, option: Argv._Option) -> bool:
            if self.is_any_of(option._options):
                if (peek := to_float(self._argv._peek)) is not None:
                    if self._set_value_property(option, property_value=peek):
                        self._argv._next
                        return True
            return False

        def set_value_floats(self, option: Argv._Option) -> bool:
            return self._set_value_property_multiple(option, to_type=to_float)

        def set_default_value_string(self, option: Argv._Option) -> bool:
            if self and (not self.is_option):
                for option in option._options:
                    if not hasattr(self._argv._values, option):
                        setattr(self._argv._values, option, self)
                        return True
            return False

        def set_default_value_strings(self, option: Argv._Option) -> bool:
            parsed = False
            peek = self
            for option in option._options:
                if hasattr(self._argv._values, option):
                    option_values = getattr(self._argv._values, option)
                else:
                    option_values = None
                while True:
                    if peek and (not peek.is_option):
                        if option_values is None:
                            option_values = []
                            setattr(self._argv._values, option, option_values)
                        option_values.append(peek)
                        self._argv._next
                        peek = self._argv._peek
                        parsed = True
                    else:
                        break
            return parsed

        def _set_value_property(self, option: Argv._Option, property_value: Any = None) -> bool:
            if property_name := option._property_name:
                setattr(self._argv._values, property_name, property_value)
                return True
            return False

        def _set_value_property_multiple(self, option: Union[Argv._Option, str],
                                         to_type: Optional[Callable] = None) -> bool:
            if isinstance(option, str): option = Argv._Option(option)  # noqa xyzzy
            if not callable(to_type):
                to_type = lambda value: value if isinstance(value, str) else None  # noqa
            if self.is_any_of(option._options):
                if property_name := option._property_name:
                    property_values = []
                    if (hasattr(self._argv._values, property_name) and
                        (existing_property_value := getattr(self._argv._values, property_name))):  # noqa
                        if isinstance(existing_property_value, list):
                            property_values[:0] = existing_property_value
                        elif (existing_property_value := to_type(existing_property_value)) is not None:
                            property_values.append(existing_property_value)
                    setattr(self._argv._values, property_name, property_values)
                    while True:
                        if not ((peek := self._argv._peek) and
                                (not peek.is_option) and ((peek := to_type(peek)) is not None)):
                            break
                        property_values.append(peek)
                        self._argv._next
                    return True
            return False

    class _Values:
        def __init__(self) -> None:
            pass

    class _OptionDefinitions:
        def __init__(self, fuzzy: bool = False) -> None:
            self._definitions = []
            self._fuzzy = fuzzy is True
            self._option_type_action_map = {
                Argv.BOOLEAN: Argv._Arg.set_value_boolean,
                Argv.STRING: Argv._Arg.set_value_string,
                Argv.STRINGS: Argv._Arg.set_value_strings,
                Argv.INTEGER: Argv._Arg.set_value_integer,
                Argv.INTEGERS: Argv._Arg.set_value_integers,
                Argv.FLOAT: Argv._Arg.set_value_float,
                Argv.FLOATS: Argv._Arg.set_value_floats,
                Argv.DEFAULT: Argv._Arg.set_default_value_string,
                Argv.DEFAULTS: Argv._Arg.set_default_value_strings
            }

        def define_option(self, option_type: int, options: List[str]) -> None:
            if isinstance(option_type, int) and isinstance(options, list):
                option_required = (option_type & Argv.REQUIRED) == Argv.REQUIRED
                option_type &= ~(Argv.REQUIRED | Argv.OPTIONAL)
                if action := self._option_type_action_map.get(option_type):
                    self._definitions.append(Argv._Option(
                        options=options, required=option_required, action=action, fuzzy=self._fuzzy))

    class _Option:
        def __init__(self,
                     options: Optional[List[str]] = None,
                     required: bool = False,
                     action: Optional[Callable] = None,
                     fuzzy: bool = True) -> None:
            self._options = to_string_list(options)
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
                    option = option[Argv._OPTION_PREFIX_LENGTH:]
                elif self._fuzzy and option.startswith(Argv._FUZZY_OPTION_PREFIX):
                    option = option[Argv._FUZZY_OPTION_PREFIX_LENGTH:]
                return option.replace("-", "_")
            return ""

    def __init__(self, *args, argv: Optional[List[str]] = None, fuzzy: bool = True,
                 strip: bool = True, skip: bool = True, escape: bool = True, delete: bool = False) -> None:
        self._argi = 0
        self._fuzzy = fuzzy is not False
        self._strip = strip is not False
        self._escape = escape is not False
        self._escaping = False
        self._delete = delete is True
        self._values = Argv._Values()
        if (len(args) == 1) and isinstance(args[0], list):
            # Here, the given args are the actual command-line arguments to process/parse.
            if not (isinstance(argv, list) and argv):
                argv = args[0]
            self._option_definitions = self._process_option_definitions()
        else:
            # Here, the given args should be the definitions for processing/parsing command-line args.
            self._option_definitions = self._process_option_definitions(*args)
        self._argv = argv if isinstance(argv, list) and argv else (sys.argv[1:] if skip is not False else sys.argv)

    @property
    def list(self) -> List[str]:
        return self._argv

    @property
    def values(self) -> Argv._Values:
        return self._values

    def parse(self, *args, report: bool = True, printf: Optional[Callable] = None) -> None:

        if (len(args) == 1) and isinstance(args[0], list):
            # Here, the given args are the actual command-line arguments to process/parse;
            # and this Argv object already should have the definitions for processing/parsing these.
            if not self._option_definitions:
                return
            self._argv = args[0]
        else:
            # Here, the given args are the definitions for processing/parsing command-line args;
            # and this Argv object already as the actual command-line arguments to process/parse.
            if not self._argv:
                return
            self._option_definitions = self._process_option_definitions(*args)  # xyzzy

        missing_options = unparsed_options = []

        if self._option_definitions:
            for arg in self:
                parsed = False
                for option in self._option_definitions._definitions:
                    if option._action(arg, option):
                        parsed = True
                        break
                if not parsed:
                    unparsed_options.append(arg)

        for option in self._option_definitions._definitions:
            if not hasattr(self._values, property_name := option._property_name):
                if option._required:
                    missing_options.append(option._option_name)
                setattr(self._values, property_name, None)

        if report is not False:
            if not callable(printf):
                printf = lambda *args, **kwargs: print(*args, **kwargs, file=sys.stderr)  # noqa
            for unparsed_arg in unparsed_options:
                printf(f"Unparsed argument: {unparsed_arg}")

        return missing_options, unparsed_options

    def _process_option_definitions(self, *args) -> None:

        def flatten(*args):
            flattened_args = []
            def flatten(*args):  # noqa
                nonlocal flattened_args
                for arg in args:
                    if isinstance(arg, (list, tuple)):
                        for itemi in range(len(arg)):
                            item = arg[itemi]
                            if isinstance(item, int) and ((itemi + 1) < len(arg)):
                                next_item = arg[itemi + 1]
                                if isinstance(next_item, tuple) or isinstance(next_item, str):
                                    if (item & Argv.OPTIONAL) != Argv.OPTIONAL:
                                        item |= Argv.REQUIRED
                            flatten(item)
                    else:
                        flattened_args.append(arg)
            flatten(args)
            return flattened_args

        option_definitions = Argv._OptionDefinitions(fuzzy=self._fuzzy)
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

    @staticmethod
    def _is_option_type(option_type: int) -> bool:
        return isinstance(option_type, int) and (option_type & ~(Argv.REQUIRED | Argv.OPTIONAL)) in Argv._TYPES

    def _is_option(self, value: str) -> bool:
        if isinstance(value, str) and (value := value.strip()):
            if value.startswith(Argv._OPTION_PREFIX) and (value := value[Argv._OPTION_PREFIX_LENGTH:].strip()):
                return True
            elif (self._fuzzy and
                  value.startswith(Argv._FUZZY_OPTION_PREFIX) and
                  (value := value[Argv._FUZZY_OPTION_PREFIX_LENGTH:].strip())):
                return True
        return False

    def __getattr__(self, name: str):
        return getattr(self._values, name) if hasattr(self._values, name) else None

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
    print(argv._option_definitions._definitions[0]._options)
    print(argv._option_definitions._definitions[0]._action)
    print(argv._option_definitions._definitions[1]._options)
    print(argv._option_definitions._definitions[1]._action)
    print(argv._option_definitions._definitions[2]._options)
    print(argv._option_definitions._definitions[2]._action)
    assert argv.values.verbose is True
    assert argv.values.debug is True
    assert argv.values.config == "file.json"
    assert argv.values.configs == ["ghi.json", "jkl.json", "mno.json"]


if True:
    # args = Argv(
    #     [Argv.STRINGS, "--config", "--conf"],
    #     [Argv.STRING, "--config", "--conf"],
    #     [Argv.INTEGERS, "--count"],
    #     [Argv.FLOATS, "--kay"]
    # )
    args = Argv(
        Argv.STRINGS, "--config", "--conf",
        Argv.STRING, "--config", "--conf",
        Argv.INTEGERS, "--count",
        Argv.FLOATS, "--kay",
        Argv.STRING, "--foo",
        Argv.STRING, "goo",
        Argv.STRING, "--import-file",
        # Argv.DEFAULT, "defaultt",
    )
    missing, unparsed = args.parse(["--config", "abc", "ghi", "-xyz",
                                    "--config", "foo", "--import-file", "secrets.json",
                                    "-count", "123", "456", "-kay", "321", "2342.234",
                                    "-123", "somefile.json", "asdfasfd"])

    print(args.values.config)
    print(args.values.count)
    print(args.values.kay)
    print('--')
    print(args.values.foo)
    print(args.values.goo)
    print(args.values.import_file)
    print(args.foobar)

    print('-------------------------------------------------------------------------')

if True:
    argv = Argv(
        # Argv.DEFAULT, "files",
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
    print(argv._option_definitions._definitions)
    print(argv._option_definitions._definitions[1])
    print(argv._option_definitions._definitions[1]._options)
    print(argv._option_definitions._definitions[1]._action)
    # import json
    # print(json.dumps(argv._definitions, indent=4, default=str))
    missing, unparsed = argv.parse(["foo", "bara", "barb", "-xyz", "goo",
                                    "-passwd", "--shell", "hoo", "-config", "configfile"])
    print('unparsed:')
    print(unparsed)
    # print(argv.values.unparsed)
    print('thedefault:')
    print(argv.values.thedefault)
    print('thedefault2:')
    print(argv.values.thedefault2)
    print('thedefaults:')
    print(argv.values.thedefaults)
    print('thedefaultb:')
    print(argv.values.thedefaultb)
    print('thedefaultfoo:')
    print(argv.values.thedefaultfoo)

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
