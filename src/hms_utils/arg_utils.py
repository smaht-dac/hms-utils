from __future__ import annotations
import sys
from typing import Any, List, Optional
from hms_utils.type_utils import to_integer


class Argv:

    BOOLEAN = 1
    FLOAT = 2
    INTEGER = 3
    STRING = 4
    STRINGS = 5

    _ESCAPE_VALUE = "--"
    _FUZZY_OPTION_PREFIX = "-"
    _FUZZY_OPTION_PREFIX_LENGTH = len(_FUZZY_OPTION_PREFIX)
    _OPTION_PREFIX = "--"
    _OPTION_PREFIX_LENGTH = len(_OPTION_PREFIX)
    _TYPES = [BOOLEAN, FLOAT, INTEGER, STRING, STRINGS]

    class _Arg(str):

        def __new__(cls, value: str, argv: Argv) -> None:
            value = (value.strip() if argv._strip else value) if isinstance(value, str) else ""
            value = super().__new__(cls, value)
            value._argv = argv
            return value

        def anyof(self, *values) -> Optional[str]:
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
            return None

        def set_boolean(self, *values) -> bool:
            if self.anyof(values):
                if self._set_property(*values, property_value=True):
                    return True
            return False

        def set_float(self, *values) -> bool:
            if self.anyof(values):
                if (value := to_integer(self._argv.peek)) is not None:  # TODO
                    if self._set_property(*values, property_value=value):
                        self._argv.next
                        return True
            return False

        def set_integer(self, *values) -> bool:
            if self.anyof(values):
                if (value := to_integer(self._argv.peek)) is not None:
                    if self._set_property(*values, property_value=value):
                        self._argv.next
                        return True
            return False

        def set_string(self, *values) -> bool:
            if self.anyof(values):
                if self._argv.peek and (not self._argv.peek.option):
                    if self._set_property(*values, property_value=self._argv.peek):
                        self._argv.next
                        return True
            return False

        def set_strings(self, *values) -> bool:
            return self.set_string_multiple(*values)

        def set_string_multiple(self, *values) -> bool:
            if self.anyof(values):
                if property_name := self._find_property_name(*values):
                    property_values = []
                    if (hasattr(self._argv._values, property_name) and
                        (existing_property_value := getattr(self._argv._values, property_name))):  # noqa
                        if isinstance(existing_property_value, list) or isinstance(existing_property_value, str):
                            property_values[:0] = existing_property_value
                    setattr(self._argv._values, property_name, property_values)
                    while True:
                        if not (self._argv.peek and (not self._argv.peek.option)):
                            break
                        property_values.append(self._argv.next)
                    return True
            return False

        def _set_property(self, *values, property_value: Any = None) -> bool:
            if property_name := self._find_property_name(*values):
                setattr(self._argv._values, property_name, property_value)
                return True
            return False

        def _find_property_name(self, *values) -> Optional[str]:
            for value in values:
                if isinstance(value, (list, tuple)):
                    for element in value:
                        if property_name := self._find_property_name(element):
                            return property_name
                elif isinstance(value, str) and (not self._argv._escaping):
                    if value := self._option_to_name(value):
                        return value
            return None

        @property
        def option(self) -> bool:
            return self._option_to_name(self) is not None

        def _option_to_name(self, value: str) -> Optional[str]:
            if isinstance(value, str) and (value := value.strip()):
                if value.startswith(Argv._OPTION_PREFIX) and (value := value[Argv._OPTION_PREFIX_LENGTH:].strip()):
                    return value
                elif (self._argv._fuzzy and
                      value.startswith(Argv._FUZZY_OPTION_PREFIX) and
                      (value := value[Argv._FUZZY_OPTION_PREFIX_LENGTH:].strip())):
                    return value
            return None

        @property
        def empty(self):
            return not self

        @property
        def null(self):
            return self.empty

    class _Values:
        unparsed = []

    def __init__(self, *args, argv: Optional[List[str]] = None, fuzzy: bool = True,
                 strip: bool = True, skip: bool = True, escape: bool = True, delete: bool = False) -> None:
        if (len(args) == 1) and isinstance(args[0], list):
            # Here, the given args are the actual command-line arguments to process/parse.
            if not (isinstance(argv, list) and argv):
                argv = args[0]
            self._definitions = []
        else:
            # Here, the given args should be the definitions for processing/parsing command-line args.
            self._definitions = self._process_definitions(*args)
        self._argv = argv if isinstance(argv, list) and argv else (sys.argv[1:] if skip is not False else sys.argv)
        self._argi = 0
        self._values = Argv._Values()
        self._fuzzy = fuzzy is not False
        self._strip = strip is not False
        self._escape = escape is not False
        self._escaping = False
        self._delete = delete is True

    def process(self, *args) -> None:
        if (len(args) == 1) and isinstance(args[0], list):
            # Here, the given args are the actual command-line arguments to process/parse;
            # and this Argv object already should have the definitions for processing/parsing these.
            if not self._definitions:
                return
            argv = auxiliary_argv = Argv()
            argv._argv = args[0]
            argv._argi = 0
            argv._fuzzy = self._fuzzy
            argv._strip = self._strip
            argv._escape = self._escape
            argv._delete = self._delete
            definitions = self._definitions
        else:
            # Here, the given args are the definitions for processing/parsing command-line args;
            # and this Argv object already as the actual command-line arguments to process/parse.
            if not self._argv:
                return
            auxiliary_argv = None
            argv = self
            definitions = self._process_definitions(*args)
        if definitions:
            for arg in argv:
                for definition in definitions:
                    definition["action"](arg, definition["options"])
        if auxiliary_argv:
            self._values = auxiliary_argv.values

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

    @property
    def list(self) -> List[str]:
        return self._argv

    @property
    def values(self) -> Argv._Values:
        return self._values

    @staticmethod
    def _process_definitions(*args) -> Optional[list]:
        def flatten(*args):
            flattened_args = []
            def flatten(*args):  # noqa
                nonlocal flattened_args
                for arg in args:
                    if isinstance(arg, (list, tuple)):
                        for item in arg:
                            flatten(item)
                    else:
                        flattened_args.append(arg)
            flatten(args)
            return flattened_args
        args = flatten(args)
        definitions = [] ; action = None ; options = []  # noqa
        for arg in args:
            if arg in Argv._TYPES:
                if action and options:
                    definitions.append({"action": action, "options": options}) ; action = None ; options = [] # noqa
                if arg == Argv.BOOLEAN: action = Argv._Arg.set_boolean  # noqa
                elif arg == Argv.FLOAT: action = Argv._Arg.set_float  # noqa
                elif arg == Argv.INTEGER: action = Argv._Arg.set_integer  # noqa
                elif arg == Argv.STRING: action = Argv._Arg.set_string  # noqa
                elif arg == Argv.STRINGS: action = Argv._Arg.set_strings  # noqa
                else:
                    action = None
                if action and options:
                    definitions.append({"action": action, "options": options}) ; action = None ; options = [] # noqa
            elif isinstance(arg, str) and (arg := arg.strip()):
                options.append(arg)
        if action and options:
            definitions.append({"action": action, "options": options}) ; action = None ; options = [] # noqa
        return definitions