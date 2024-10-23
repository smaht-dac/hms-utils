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
    REQUIRED = 0x1000

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
                            return self._find_property_name(*values)
                elif match(value):
                    return self._find_property_name(*values)
            return False

        def set_boolean(self, *values) -> bool:
            if self.anyof(values):
                if self._set_property(*values, property_value=True):
                    return True
            return False

        def set_string(self, *values) -> bool:
            if self.anyof(values):
                if (peek := self._argv.peek) and (not peek.option):
                    if self._set_property(*values, property_value=peek):
                        self._argv.next
                        return True
            return False

        # def set_strings(self, *values, is_type: Optional[Callable] = None) -> bool:
        def set_strings(self, *values) -> bool:
            return self._set_property_multiple(*values)

        def set_integer(self, *values) -> bool:
            if self.anyof(values):
                if (peek := to_integer(self._argv.peek)) is not None:
                    if self._set_property(*values, property_value=peek):
                        self._argv.next
                        return True
            return False

        def set_integers(self, *values) -> bool:
            return self._set_property_multiple(*values, to_type=to_integer)

        def set_float(self, *values) -> bool:
            if self.anyof(values):
                if (peek := to_float(self._argv.peek)) is not None:
                    if self._set_property(*values, property_value=peek):
                        self._argv.next
                        return True
            return False

        def set_floats(self, *values) -> bool:
            return self._set_property_multiple(*values, to_type=to_float)

        def _set_property(self, *values, property_value: Any = None) -> bool:
            if property_name := self._find_property_name(*values):
                setattr(self._argv._values, property_name, property_value)
                return True
            return False

        def _set_property_multiple(self, *values, to_type: Optional[Callable] = None) -> bool:
            if not callable(to_type):
                to_type = lambda value: value if isinstance(value, str) else None  # noqa
            if self.anyof(values):
                if property_name := self._find_property_name(*values):
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

        def _find_property_name(self, *values) -> Optional[str]:
            return self._argv._find_property_name(*values)

        def _property_name_from_option(self, value: str) -> Optional[str]:
            return self._argv._property_name_from_option(value)

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
        def __init__(self) -> None:
            self._options = []
            self._option_property_names = []
            self._default_property_names = []
            self._defaults_property_name = ""

        @property
        def options(self) -> List[Argv._OptionDefinition]:
            return self._options

        def add_option(self, value: Argv._OptionDefinition) -> None:
            if isinstance(value, Argv._OptionDefinition):
                self._options.append(value)

        @property
        def option_property_names(self) -> List[str]:
            return self._option_property_names

        def add_option_property_name(self, property_name: str) -> None:
            if isinstance(property_name, str) and (property_name := property_name.strip()):
                if (property_name := property_name.replace("-", "_")) not in self._option_property_names:
                    self._option_property_names.append(property_name)

        @property
        def default_property_names(self) -> List[str]:
            return self._default_property_names

        def add_default_property_names(self, value: Union[List[str], str]) -> None:
            value = value if isinstance(value, list) else [value]
            value = [item.strip() for item in value if isinstance(item, str) and item.strip()]
            self._default_property_names.extend(value)

        @property
        def defaults_property_name(self) -> str:
            return self._defaults_property_name

        @defaults_property_name.setter
        def defaults_property_name(self, value: str) -> None:
            self._defaults_property_name = value if isinstance(value, str) and (value := value.strip()) else ""

    class _OptionDefinition:
        def __init__(self, options: Union[List[str], str], action: Callable, required: bool = False) -> None:
            self._options = options
            self._action = action
            self._required = required is True

        @property
        def options(self) -> List[str]:
            return self._options

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
            return self._action(arg, self._options)

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
        self._option_definitions = Argv._OptionDefinitions()
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
            self._process_option_definitions(*args)
            option_definitions = self._option_definitions
        if option_definitions:
            for arg in argv:
                parsed = False
                for option in option_definitions._options:
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
                        if (not parsed) and option_definitions.defaults_property_name:
                            if not hasattr(argv._values, option_definitions.defaults_property_name):
                                setattr(argv._values, option_definitions.defaults_property_name, [arg])
                            else:
                                getattr(argv._values, option_definitions.defaults_property_name).append(arg)
                            parsed = True
                    if not parsed:
                        getattr(argv._values, argv._unparsed_property_name).append(arg)
        for property_name in option_definitions.option_property_names:
            if not hasattr(argv._values, property_name):
                setattr(argv._values, property_name, None)
        if auxiliary_argv:
            self._values = auxiliary_argv.values
        if report is not False:
            if not callable(printf):
                printf = lambda *args, **kwargs: print(*args, **kwargs, file=sys.stderr)  # noqa
            for unparsed_arg in getattr(self._values, self. _unparsed_property_name):
                printf(f"Unparsed argument: {unparsed_arg}")

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
                # for arg in args:
                for argi in range(len(args)):
                    arg = args[argi]
                    if isinstance(arg, (list, tuple)):
                        # for item in arg:
                        for iitem in range(len(arg)):
                            item = arg[iitem]
                            if isinstance(item, int):
                                # import pdb ; pdb.set_trace()  # noqa
                                if (iitem + 1) < len(arg):
                                    next_item = arg[iitem + 1]
                                    if isinstance(next_item, tuple):
                                        # item |= Argv.REQUIRED
                                        # required = True
                                        pass
                            flatten(item)
                    else:
                        if isinstance(arg, int):
                            print(args)
                            print(arg)
                            # import pdb ; pdb.set_trace()  # noqa
                            pass
                        flattened_args.append(arg)
            flatten(args)
            return flattened_args

        def add_option_definition(options: List[str], action: Union[str, Callable]) -> None:
            nonlocal self
            if action == Argv.DEFAULT:
                self._option_definitions.add_default_property_names(options)
            elif action == Argv.DEFAULTS:
                self._option_definitions.defaults_property_name = options[0]
            elif callable(action):
                self._option_definitions.add_option(Argv._OptionDefinition(options=options, action=action))

        args = flatten(args)
        action = None ; options = []  # noqa
        for arg in args:
            if arg in Argv._TYPES:
                if action and options:
                    add_option_definition(options, action)
                    action = None ; options = []  # noqa
                if arg == Argv.BOOLEAN: action = Argv._Arg.set_boolean  # noqa
                elif arg == Argv.STRING: action = Argv._Arg.set_string  # noqa
                elif arg == Argv.STRINGS: action = Argv._Arg.set_strings  # noqa
                elif arg == Argv.INTEGER: action = Argv._Arg.set_integer  # noqa
                elif arg == Argv.INTEGERS: action = Argv._Arg.set_integers  # noqa
                elif arg == Argv.FLOAT: action = Argv._Arg.set_float  # noqa
                elif arg == Argv.FLOATS: action = Argv._Arg.set_floats  # noqa
                elif arg in [Argv.DEFAULT, Argv.DEFAULTS]: action = arg  # noqa
                else:
                    action = None
                if action and options:
                    add_option_definition(options, action)
                    action = None ; options = []  # noqa
            elif isinstance(arg, str) and (arg := arg.strip()):
                if not options:
                    if arg.startswith(Argv._OPTION_PREFIX):
                        property_name = arg[Argv._OPTION_PREFIX_LENGTH:]
                    elif self._fuzzy and arg.startswith(Argv._FUZZY_OPTION_PREFIX):
                        property_name = arg[Argv._FUZZY_OPTION_PREFIX_LENGTH:]
                    else:
                        property_name = arg
                    self._option_definitions.add_option_property_name(property_name)
                options.append(arg)
        if options:
            if not action:
                action = Argv._Arg.set_boolean
            add_option_definition(options, action)
            action = None ; options = []  # noqa

    def _find_property_name(self, *values) -> Optional[str]:
        for value in values:
            if isinstance(value, (list, tuple)):
                for element in value:
                    if property_name := self._find_property_name(element):
                        return property_name
            elif isinstance(value, str) and (not self._escaping):
                if value := self._property_name_from_option(value):
                    return value
        return None

    def _property_name_from_option(self, value: str) -> Optional[str]:
        if isinstance(value, str) and (value := value.strip()):
            if value.startswith(Argv._OPTION_PREFIX) and (value := value[Argv._OPTION_PREFIX_LENGTH:].strip()):
                return value.replace("-", "_")
            elif (self._fuzzy and
                  value.startswith(Argv._FUZZY_OPTION_PREFIX) and
                  (value := value[Argv._FUZZY_OPTION_PREFIX_LENGTH:].strip())):
                return value.replace("-", "_")
            else:
                return value.replace("-", "_")
        return None

    def _is_option(self, value: str) -> bool:
        if isinstance(value, str) and (value := value.strip()):
            if value.startswith(Argv._OPTION_PREFIX) and (value := value[Argv._OPTION_PREFIX_LENGTH:].strip()):
                return True
            elif (self._fuzzy and
                  value.startswith(Argv._FUZZY_OPTION_PREFIX) and
                  (value := value[Argv._FUZZY_OPTION_PREFIX_LENGTH:].strip())):
                return True
        return False

# args = Argv({"foo": "bar"})


if False:
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
    args.parse(["--config", "abc", "ghi", "-xyz", "--config", "foo", "--import-file", "secrets.json",
                "-count", "123", "456", "-kay", "321", "2342.234", "-123", "somefile.json", "asdfasfd"])

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
        Argv.STRINGS, ("--secrets", "--secret"),
        Argv.STRINGS, ["--merge"],
        Argv.STRINGS, ["--includes", "--include", "--imports", "--import",
                       "--import-config", "--import-configs", "--import-conf"],
        Argv.STRINGS, ["--include-secrets", "--include-secret", "--import-secrets", "--import-secret"],
        Argv.BOOLEAN, ["--list"],
        Argv.BOOLEAN, ["--tree"],
        Argv.BOOLEAN, ["--dump"],
        Argv.BOOLEAN, ["--json"],
        Argv.BOOLEAN, ["--formatted", "--format"],
        Argv.BOOLEAN, ["--jsonf"],
        Argv.BOOLEAN, ["--raw"],
        Argv.BOOLEAN, ["--verbose"],
        Argv.BOOLEAN, ["--debug"],
        Argv.STRINGS, ["--shell", "-shell", "--script", "-script", "--scripts", "-scripts", "--command", "-command",
                       "--commands", "-commands", "--function", "-function", "--functions", "-functions"],
        Argv.STRING, ["--password", "--passwd"],
        Argv.STRING, ["--exports", "--export"],
        Argv.STRING, ["--exports-file", "--export-file"],
        Argv.DEFAULT, "thedefault",
        Argv.DEFAULTS, "thedefaults",
        Argv.DEFAULT, "thedefaultb",
        Argv.DEFAULTS, "thedefaultfoo",
        #    Argv.DEFAULTS, "thedefaults"
    )
    # import json
    # print(json.dumps(argv._definitions, indent=4, default=str))
    argv.parse(["foo", "bara", "barb", "-xyz", "goo"])
    print('unparsed:')
    print(argv.values.unparsed)
    print('thedefault:')
    print(argv.values.thedefault)
    print('thedefaultb:')
    print(argv.values.thedefaultb)
    print('thedefaults:')
    print(argv.values.thedefaults)
    print('thedefaultfoo:')
    print(argv.values.thedefaultfoo)
