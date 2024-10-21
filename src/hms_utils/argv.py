from __future__ import annotations
import json
import sys
from typing import Any, Callable, List, Optional
from uuid import uuid4 as uuid
from hms_utils.type_utils import to_float, to_integer


class Argv:

    BOOLEAN = uuid()
    FLOAT = uuid()
    FLOATS = uuid()
    INTEGER = uuid()
    INTEGERS = uuid()
    STRING = uuid()
    STRINGS = uuid()

    _ESCAPE_VALUE = "--"
    _FUZZY_OPTION_PREFIX = "-"
    _FUZZY_OPTION_PREFIX_LENGTH = len(_FUZZY_OPTION_PREFIX)
    _OPTION_PREFIX = "--"
    _OPTION_PREFIX_LENGTH = len(_OPTION_PREFIX)
    _TYPES = [BOOLEAN, FLOAT, FLOATS, INTEGER, INTEGERS, STRING, STRINGS]
    _UNPARSED_PROPERTY_NAME = "unparsed"

    class _Arg(str):

        def __new__(cls, value: str, argv: Argv) -> None:
            value = (value.strip() if argv._strip else value) if isinstance(value, str) else ""
            value = super().__new__(cls, value)
            value._argv = argv
            return value

        @property
        def option(self) -> bool:
            return self._property_name_from_option(self) is not None

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

        def set_strings(self, *values, is_type: Optional[Callable] = None) -> bool:
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

        def _set_property(self, *values, property_value: Any = None) -> bool:
            if property_name := self._find_property_name(*values):
                setattr(self._argv._values, property_name, property_value)
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
            setattr(self, unparsed_property_name, [])

    def __init__(self, *args, argv: Optional[List[str]] = None, fuzzy: bool = True,
                 strip: bool = True, skip: bool = True, escape: bool = True, delete: bool = False,
                 unparsed_property_name: Optional[str] = None) -> None:
        self._argi = 0
        self._fuzzy = fuzzy is not False
        self._strip = strip is not False
        self._escape = escape is not False
        self._escaping = False
        self._delete = delete is True
        self._unparsed_property_name = (self._property_name_ize(unparsed_property_name)
                                        if (isinstance(unparsed_property_name, str) and
                                            unparsed_property_name)
                                        else Argv._UNPARSED_PROPERTY_NAME)
        self._values = Argv._Values(unparsed_property_name=self._unparsed_property_name)
        if (len(args) == 1) and isinstance(args[0], list):
            # Here, the given args are the actual command-line arguments to process/parse.
            if not (isinstance(argv, list) and argv):
                argv = args[0]
            self._definitions = []
            self._property_names = []
        else:
            # Here, the given args should be the definitions for processing/parsing command-line args.
            self._definitions, self._property_names = self._process_definitions(*args)
        self._argv = argv if isinstance(argv, list) and argv else (sys.argv[1:] if skip is not False else sys.argv)

    def parse(self, *args) -> None:
        return self.process(*args)

    def process(self, *args) -> None:
        if (len(args) == 1) and isinstance(args[0], list):
            # Here, the given args are the actual command-line arguments to process/parse;
            # and this Argv object already should have the definitions for processing/parsing these.
            if not self._definitions:
                return
            argv = auxiliary_argv = Argv(unparsed_property_name=self._unparsed_property_name)
            argv._argv = args[0]
            argv._argi = 0
            argv._fuzzy = self._fuzzy
            argv._strip = self._strip
            argv._escape = self._escape
            argv._delete = self._delete
            definitions = self._definitions
            property_names = self._property_names
        else:
            # Here, the given args are the definitions for processing/parsing command-line args;
            # and this Argv object already as the actual command-line arguments to process/parse.
            if not self._argv:
                return
            auxiliary_argv = None
            argv = self
            definitions, property_names = self._process_definitions(*args)
        if definitions:
            for arg in argv:
                parsed = False
                for definition in definitions:
                    if definition["action"](arg, definition["options"]):
                        parsed = True
                if not parsed:
                    getattr(argv._values, argv._unparsed_property_name).append(arg)
        for property_name in property_names:
            if not hasattr(argv._values, property_name):
                setattr(argv._values, property_name, None)
        if auxiliary_argv:
            self._values = auxiliary_argv.values

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

    def _process_definitions(self, *args) -> Optional[list]:
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
        definitions = [] ; property_names = [] ; action = None ; options = []  # noqa
        for arg in args:
            if arg in Argv._TYPES:
                if action and options:
                    definitions.append({"action": action, "options": options,
                                        "name": self._property_name_from_option(options[0])})
                    action = None ; options = []  # noqa
                if arg == Argv.BOOLEAN: action = Argv._Arg.set_boolean  # noqa
                elif arg == Argv.STRING: action = Argv._Arg.set_string  # noqa
                elif arg == Argv.STRINGS: action = Argv._Arg.set_strings  # noqa
                elif arg == Argv.INTEGER: action = Argv._Arg.set_integer  # noqa
                elif arg == Argv.INTEGERS: action = Argv._Arg.set_integers  # noqa
                elif arg == Argv.FLOAT: action = Argv._Arg.set_float  # noqa
                elif arg == Argv.FLOATS: action = Argv._Arg.set_floats  # noqa
                else:
                    action = None
                if action and options:
                    definitions.append({"action": action, "options": options,
                                        "name": self._property_name_from_option(options[0])})
                    action = None ; options = []  # noqa
            elif isinstance(arg, str) and (arg := arg.strip()):
                if not options:
                    if arg.startswith(Argv._OPTION_PREFIX):
                        property_name = arg[Argv._OPTION_PREFIX_LENGTH:]
                    elif self._fuzzy and arg.startswith(Argv._FUZZY_OPTION_PREFIX):
                        property_name = arg[Argv._FUZZY_OPTION_PREFIX_LENGTH:]
                    else:
                        property_name = arg
                    if property_name not in property_names:
                        property_names.append(property_name)
                options.append(arg)
        if options:
            if not action:
                action = Argv._Arg.set_boolean
            definitions.append({"action": action, "options": options,
                                "name": self._property_name_from_option(options[0])})
            action = None ; options = []  # noqa
        return definitions, property_names

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
                return self._property_name_ize(value)
            elif (self._fuzzy and
                  value.startswith(Argv._FUZZY_OPTION_PREFIX) and
                  (value := value[Argv._FUZZY_OPTION_PREFIX_LENGTH:].strip())):
                return self._property_name_ize(value)
        return None

    @staticmethod
    def _property_name_ize(value: str) -> Optional[str]:
        return value.replace("-", "_") if isinstance(value, str) else None
