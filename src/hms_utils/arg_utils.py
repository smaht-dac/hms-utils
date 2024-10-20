from __future__ import annotations
import sys
from typing import Any, List, Optional
from hms_utils.type_utils import to_integer


class Argv:

    _OPTION_PREFIX = "--"
    _OPTION_PREFIX_LENGTH = len(_OPTION_PREFIX)
    _FUZZY_OPTION_PREFIX = "-"
    _FUZZY_OPTION_PREFIX_LENGTH = len(_FUZZY_OPTION_PREFIX)
    _ESCAPE_VALUE = "--"

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

        def set_string_multiple(self, *values) -> bool:
            if self.anyof(values):
                if property_name := self._find_property_name(*values):
                    property_values = []
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

    def __init__(self, argv: Optional[List[str]] = None, fuzzy: bool = True,
                 strip: bool = True, skip: bool = True, escape: bool = True, delete: bool = False) -> None:
        self._argv = argv if isinstance(argv, list) and argv else (sys.argv[1:] if skip is not False else sys.argv)
        self._argi = 0
        self._values = Argv._Values()
        self._fuzzy = fuzzy is not False
        self._strip = strip is not False
        self._escape = escape is not False
        self._escaping = False
        self._delete = delete is True

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
