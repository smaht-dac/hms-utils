from __future__ import annotations
import sys
from typing import Any, Callable, List, Optional, Union
from hms_utils.type_utils import to_float, to_integer


class Argv:

    class _TYPE:
        def __init__(self, action: Union[str, Callable], required: bool = False) -> None:
            self._action = action if isinstance(action, (str, Callable)) else None
            self._required = required is True

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
    _UNPARSED_PROPERTY_NAME = "unparsed"

    class _Arg(str):

        def __new__(cls, value: str, argv: Argv) -> None:
            value = (value.strip() if argv._strip else value) if isinstance(value, str) else ""
            value = super().__new__(cls, value)
            value._argv = argv
            return value

        @property
        def option(self) -> bool:
            return self._argv._is_option(self)

        def anyof(self, *values) -> bool:
            def match(value: Any) -> bool:
                nonlocal self
                if self._argv._escaping:
                    return False
                if isinstance(value, str) and (value := value.strip()):
                    if ((self == value) or
                        (self._argv._fuzzy and value.startswith(Argv._OPTION_PREFIX) and
                         (self == Argv._FUZZY_OPTION_PREFIX + value[Argv._OPTION_PREFIX_LENGTH:]))):
                        return True
                return False
            for value in values:
                if isinstance(value, (list, tuple)):
                    for element in value:
                        if self.anyof(element):
                            return True
                elif match(value):
                    return True
            return False

        def set_value_boolean(self, option: Argv._OptionDefinition) -> bool:
            if isinstance(option, str): option = Argv._OptionDefinition(option)  # noqa xyzzy
            if self.anyof(option.options):
                if self._set_value_property(option, property_value=True):
                    return True
            return False

        def set_value_string(self, option: Argv._OptionDefinition) -> bool:
            if isinstance(option, str): option = Argv._OptionDefinition(option)  # noqa xyzzy
            if self.anyof(option.options):
                if (peek := self._argv.peek) and (not peek.option):
                    if self._set_value_property(option, property_value=peek):
                        self._argv.next
                        return True
            return False

        def set_value_strings(self, option: Argv._OptionDefinition) -> bool:
            return self._set_value_property_multiple(option)

        def set_value_integer(self, option: Argv._OptionDefinition) -> bool:
            if self.anyof(option.options):
                if (peek := to_integer(self._argv.peek)) is not None:
                    if self._set_value_property(option, property_value=peek):
                        self._argv.next
                        return True
            return False

        def set_value_integers(self, option: Argv._OptionDefinition) -> bool:
            return self._set_value_property_multiple(option, to_type=to_integer)

        def set_value_float(self, option: Argv._OptionDefinition) -> bool:
            if self.anyof(option.options):
                if (peek := to_float(self._argv.peek)) is not None:
                    if self._set_value_property(option, property_value=peek):
                        self._argv.next
                        return True
            return False

        def set_value_floats(self, option: Argv._OptionDefinition) -> bool:
            return self._set_value_property_multiple(option, to_type=to_float)

        def set_string_for_default(self, default: str) -> bool:
            if self and (not self.option):
                if isinstance(default, str) and default and (not hasattr(self._argv._values, default)):
                    setattr(self._argv._values, default, self)
                    # self._argv.next
                    return True
            return False

        def set_strings_for_defaults(self, default: str) -> bool:
            parsed = False
            if isinstance(default, str) and default:
                peek = self
                if hasattr(self._argv._values, default):
                    defaults_values = getattr(self._argv._values, default)
                else:
                    defaults_values = None
                while True:
                    if peek and (not peek.option):
                        if defaults_values is None:
                            defaults_values = []
                            setattr(self._argv._values, default, defaults_values)
                        defaults_values.append(peek)
                        self._argv.next
                        peek = self._argv.peek
                        parsed = True
                    else:
                        break
            return parsed

        def _set_value_property(self, option: Argv._OptionDefinition, property_value: Any = None) -> bool:
            if property_name := option.property_name:
                setattr(self._argv._values, property_name, property_value)
                return True
            return False

        def _set_value_property_multiple(self, option: Union[Argv._OptionDefinition, str],
                                         to_type: Optional[Callable] = None) -> bool:
            if isinstance(option, str): option = Argv._OptionDefinition(option)  # noqa xyzzy
            if not callable(to_type):
                to_type = lambda value: value if isinstance(value, str) else None  # noqa
            if self.anyof(option.options):
                if property_name := option.property_name:
                    property_values = []
                    if (hasattr(self._argv._values, property_name) and
                        (existing_property_value := getattr(self._argv._values, property_name))):  # noqa
                        if isinstance(existing_property_value, list):
                            property_values[:0] = existing_property_value
                        elif (existing_property_value := to_type(existing_property_value)) is not None:
                            property_values.append(existing_property_value)
                    setattr(self._argv._values, property_name, property_values)
                    while True:
                        if not ((peek := self._argv.peek) and
                                (not peek.option) and ((peek := to_type(peek)) is not None)):
                            break
                        property_values.append(peek)
                        self._argv.next
                    return True
            return False

        @property
        def empty(self):
            return not self

        @property
        def null(self):
            return self.empty

    class _Values:
        def __init__(self, unparsed_property_name: Optional[str] = None):
            self._unparsed_property_name = unparsed_property_name
            setattr(self, unparsed_property_name, [])

    class _OptionDefinitions:
        def __init__(self, fuzzy: bool = False) -> None:
            self._definitions = []
            self._default_property_names = []
            self._defaults_property_names = ""
            self._fuzzy = fuzzy is True

        def define_option(self, option_type: int, options: List[str]) -> None:
            if not (isinstance(option_type, int) and isinstance(options, list)):
                return
            option_required = (option_type & Argv.REQUIRED) == Argv.REQUIRED
            option_type &= ~(Argv.REQUIRED | Argv.OPTIONAL)
            action = None
            if option_type == Argv.BOOLEAN: action = Argv._Arg.set_value_boolean  # noqa
            elif option_type == Argv.STRING: action = Argv._Arg.set_value_string  # noqa
            elif option_type == Argv.STRINGS: action = Argv._Arg.set_value_strings  # noqa
            elif option_type == Argv.INTEGER: action = Argv._Arg.set_value_integer  # noqa
            elif option_type == Argv.INTEGERS: action = Argv._Arg.set_value_integers  # noqa
            elif option_type == Argv.FLOAT: action = Argv._Arg.set_value_float  # noqa
            elif option_type == Argv.FLOATS: action = Argv._Arg.set_value_floats  # noqa
            elif option_type == Argv.DEFAULT:
                for default_property_name in options:
                    self._definitions.append(Argv._OptionDefinition(
                        default=default_property_name, required=option_required))
            elif option_type == Argv.DEFAULTS:
                for defaults_property_name in options:
                    self._definitions.append(Argv._OptionDefinition(
                        defaults=defaults_property_name, required=option_required))
            if action:
                self._definitions.append(Argv._OptionDefinition(
                    options=options, required=option_required, action=action, fuzzy=self._fuzzy))

        @property
        def definitions(self) -> List[Argv._OptionDefinition]:
            return self._definitions

        @property
        def default_property_names(self) -> List[str]:
            return self._default_property_names

        @property
        def defaults_property_names(self) -> str:
            return self._defaults_property_names

    class _OptionDefinition:
        def __init__(self,
                     options: Optional[List[str]] = None,
                     default: Optional[str] = None,
                     defaults: Optional[str] = None,
                     required: bool = False,
                     action: Optional[Callable] = None,
                     fuzzy: bool = True) -> None:
            if isinstance(default, str) and (default := default.strip()):
                self._default = default.replace("-", "_")
                self._defaults = None
                self._options = []
                self._required = required is True
                self._fuzzy = False
                self._action = Argv._Arg.set_string_for_default
            elif isinstance(defaults, str) and (defaults := defaults.strip()):
                self._default = default
                self._defaults = defaults.replace("-", "_")
                self._options = []
                self._required = required is True
                self._fuzzy = False
                self._action = Argv._Arg.set_strings_for_defaults
            else:
                self._default = None
                self._defaults = None
                self._options = (options if isinstance(options, list)
                                 else ([options] if isinstance(options, str) else []))
                self._required = required is True
                self._fuzzy = fuzzy is not True
                self._action = action if callable(action) else lambda: None

        @property
        def options(self) -> List[str]:
            return self._options

        @property
        def default(self) -> Optional[str]:
            return self._default

        @property
        def defaults(self) -> Optional[str]:
            return self._defaults

        @property
        def option_name(self) -> str:
            if self._default:
                return self._default
            elif self._defaults:
                return self._defaults
            elif self._options:
                return self._options[0]
            return ""

        @property
        def property_name(self) -> str:
            if self._default:
                return self._default
            elif self._defaults:
                return self._defaults
            elif self._options:
                return self._property_namify(self._options[0]) if self._options else ""
            return ""

        def _property_namify(self, option: str) -> str:
            if isinstance(option, str) and (option := option.strip()):
                if option.startswith(Argv._OPTION_PREFIX):
                    option = option[Argv._OPTION_PREFIX_LENGTH:]
                elif self._fuzzy and option.startswith(Argv._FUZZY_OPTION_PREFIX):
                    option = option[Argv._FUZZY_OPTION_PREFIX_LENGTH:]
                return option.replace("-", "_")
            return ""

        @property
        def required(self) -> bool:
            return self._required

        @options.setter
        def options(self, options: Union[List[str], str]) -> None:
            options = (options if isinstance(options, list)
                       else ([options] if isinstance(options, str) and (options := options.strip()) else []))
            self._options = [item for item in options if isinstance(item, str)]

        @property
        def action(self) -> Callable:
            return self._action

        @action.setter
        def action(self, action: Callable) -> None:
            self._action = action if callable(action) else lambda: None

        def call_action(self, arg: Argv._Arg) -> bool:
            if self._default:
                return self._action(arg, self._default)
            elif self._defaults:
                return self._action(arg, self._defaults)
            elif self._options:
                # import pdb ; pdb.set_trace()  # noqa
                # x = Argv._Arg.new_set_string(arg, self)
                return self._action(arg, self)
                # return self._action(arg, self._options)

    def __init__(self, *args, argv: Optional[List[str]] = None, fuzzy: bool = True,
                 strip: bool = True, skip: bool = True, escape: bool = True, delete: bool = False,
                 unparsed_property_name: Optional[str] = None) -> None:
        self._argi = 0
        self._fuzzy = fuzzy is not False
        self._strip = strip is not False
        self._escape = escape is not False
        self._escaping = False
        self._delete = delete is True
        self._unparsed_property_name = (unparsed_property_name
                                        if (isinstance(unparsed_property_name, str) and
                                            unparsed_property_name)
                                        else Argv._UNPARSED_PROPERTY_NAME)
        self._values = Argv._Values(unparsed_property_name=self._unparsed_property_name)
        self._option_definitions = Argv._OptionDefinitions(self._fuzzy)
        if (len(args) == 1) and isinstance(args[0], list):
            # Here, the given args are the actual command-line arguments to process/parse.
            if not (isinstance(argv, list) and argv):
                argv = args[0]
        else:
            # Here, the given args should be the definitions for processing/parsing command-line args.
            self._process_option_definitions(*args)
        self._argv = argv if isinstance(argv, list) and argv else (sys.argv[1:] if skip is not False else sys.argv)

    def parse(self, *args, report: bool = True, printf: Optional[Callable] = None) -> None:
        return self._process(*args, report=report, printf=printf)

    def _process(self, *args, report: bool = True, printf: Optional[Callable] = None) -> None:

        if (len(args) == 1) and isinstance(args[0], list):
            # Here, the given args are the actual command-line arguments to process/parse;
            # and this Argv object already should have the definitions for processing/parsing these.
            if not self._option_definitions:
                return
            argv = auxiliary_argv = Argv(unparsed_property_name=self._unparsed_property_name)
            argv._argv = args[0]
            argv._argi = 0
            argv._fuzzy = self._fuzzy
            argv._strip = self._strip
            argv._escape = self._escape
            argv._delete = self._delete
            option_definitions = self._option_definitions
        else:
            # Here, the given args are the definitions for processing/parsing command-line args;
            # and this Argv object already as the actual command-line arguments to process/parse.
            if not self._argv:
                return
            auxiliary_argv = None
            argv = self
            self._process_option_definitions(*args)  # xyzzy
            option_definitions = self._option_definitions

        missing_options = []
        unparsed_options = []

        if option_definitions:
            for arg in argv:
                parsed = False
                for option in option_definitions._definitions:
                    if option.call_action(arg):
                        parsed = True
                        break
                if not parsed:
                    if not arg.option:
                        if option_definitions.default_property_names:
                            for default_property_name in option_definitions.default_property_names:
                                if not hasattr(argv._values, default_property_name):
                                    setattr(argv._values, default_property_name, arg)
                                    parsed = True
                                    break
                        if (not parsed) and option_definitions.defaults_property_names:
                            if not hasattr(argv._values, option_definitions.defaults_property_names):
                                setattr(argv._values, option_definitions.defaults_property_names, [arg])
                            else:
                                getattr(argv._values, option_definitions.defaults_property_names).append(arg)
                            parsed = True
                    if not parsed:
                        unparsed_options.append(arg)
                        getattr(argv._values, argv._unparsed_property_name).append(arg)

        # Check for required arguments.
        for option in option_definitions.definitions:
            if not hasattr(argv._values, property_name := option.property_name):
                if option.required:
                    missing_options.append(option.option_name)
                setattr(argv._values, property_name, None)
        # End check for required arguments.

        for property_name in option_definitions.default_property_names + [option_definitions.defaults_property_names]:
            if not hasattr(argv._values, property_name):
                pass
                setattr(argv._values, property_name, None)
        if auxiliary_argv:
            self._values = auxiliary_argv.values

        if report is not False:
            if not callable(printf):
                printf = lambda *args, **kwargs: print(*args, **kwargs, file=sys.stderr)  # noqa
            for unparsed_arg in getattr(self._values, self. _unparsed_property_name):
                printf(f"Unparsed argument: {unparsed_arg}")

        return missing_options, unparsed_options

    @property
    def list(self) -> List[str]:
        return self._argv

    @property
    def values(self) -> Argv._Values:
        return self._values

    @property
    def peek(self) -> Optional[str]:
        return Argv._Arg(self._argv[self._argi], self) if self._argi < len(self._argv) else Argv._Arg(None, self)

    @property
    def next(self) -> Optional[str]:
        if (value := self.peek) is not None:
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

    def _process_option_definitions(self, *args) -> None:

        def flatten(*args):
            flattened_args = []
            def flatten(*args):  # noqa
                nonlocal flattened_args
                for arg in args:
                    if isinstance(arg, (list, tuple)):
                        for itemi in range(len(arg)):
                            item = arg[itemi]
                            if isinstance(item, int):
                                if (itemi + 1) < len(arg):
                                    next_item = arg[itemi + 1]
                                    if isinstance(next_item, tuple) or isinstance(next_item, str):
                                        if (item & Argv.OPTIONAL) != Argv.OPTIONAL:
                                            item |= Argv.REQUIRED
                            flatten(item)
                    else:
                        flattened_args.append(arg)
            flatten(args)
            return flattened_args

        args = flatten(args)
        option_type = None ; options = [] ; parsing_options = None  # noqa
        for arg in args:
            if self._is_option_type(arg):
                if (parsing_options is True) and option_type and options:
                    self._option_definitions.define_option(option_type, options)
                    option_type = None
                    options = []
                parsing_options = False
                option_type = arg
            elif isinstance(arg, str) and (arg := arg.strip()):
                if (parsing_options is False) and option_type and options:
                    self._option_definitions.define_option(option_type, options)
                    option_type = None
                    options = []
                parsing_options = True
                options.append(arg)
        if options:
            if not option_type:
                option_type = Argv.BOOLEAN
            self._option_definitions.define_option(option_type, options)
        return isinstance(option_type, int) and (option_type & ~(Argv.REQUIRED | Argv.OPTIONAL)) in Argv._TYPES

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
# import pdb ; pdb.set_trace()  # noqa


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
    print(argv._option_definitions.definitions[0].options)
    print(argv._option_definitions.definitions[0].action)
    print(argv._option_definitions.definitions[1].options)
    print(argv._option_definitions.definitions[1].action)
    print(argv._option_definitions.definitions[2].options)
    print(argv._option_definitions.definitions[2].action)
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
        unparsed_property_name="foobar"
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
    print(args.values.foobar)

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
    print(argv._option_definitions.definitions)
    print(argv._option_definitions.definitions[1])
    print(argv._option_definitions.definitions[1].options)
    print(argv._option_definitions.definitions[1].action)
    # import json
    # print(json.dumps(argv._definitions, indent=4, default=str))
    missing, unparsed = argv.parse(["foo", "bara", "barb", "-xyz", "goo",
                                    "-passwd", "--shell", "hoo", "-config", "configfile"])
    print('unparsed:')
    print(argv.values.unparsed)
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
