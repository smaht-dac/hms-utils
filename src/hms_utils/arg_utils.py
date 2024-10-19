from __future__ import annotations
import sys
from typing import Any, List, Optional
from hms_utils.type_utils import to_integer


class Argv:

    class Arg(str):

        def __new__(cls, value: str, args: Argv) -> None:
            value = (value.strip() if args._strip else value) if isinstance(value, str) else ""
            value = super().__new__(cls, value)
            value._argv = args
            return value

        def anyof(self, *values) -> bool:
            def match(value: Any) -> bool:
                nonlocal self
                return (isinstance(value, str) and
                        ((self == value) or (self._argv._fuzzy and value.startswith("--") and (self == value[1:]))))
            for value in values:
                if isinstance(value, (list, tuple)):
                    for element in value:
                        if self.anyof(element):
                            return True
                elif match(value):
                    return True
            return False

        def set_boolean(self, *values) -> bool:
            if self.anyof(values):
                if self._set_property(*values, property_value=True) is not None:
                    return True
            return False

        def set_integer(self, *values) -> bool:
            if self.anyof(values):
                if (value := to_integer(self._argv.peek)) is not None:
                    if self._set_property(*values, property_value=value) is not None:
                        self._argv.next
                        return True
            return False

        def set_string(self, *values) -> bool:
            if self.anyof(values):
                if ((value := self._argv.peek) is not None) and (not value.option):
                    if self._set_property(*values, property_value=value) is not None:
                        self._argv.next
                        return True
            return False

        def _set_property(self, *values, property_value: Any = None) -> Optional[object]:
            def find_target_object(*values) -> Optional[object]:
                for value in values:
                    if (not isinstance(value, str)) and hasattr(value, "__dict__"):
                        return value
                return None
            def find_property_name(*value) -> Optional[str]:  # noqa
                for value in values:
                    if isinstance(value, (list, tuple)):
                        for element in value:
                            if property_name := find_property_name(element):
                                return property_name
                    elif isinstance(value, str):
                        if value.startswith("--") and (value := value[2:].strip()):
                            return value
                        elif self._argv._fuzzy and value.startswith("-") and (value := value[2:].strip()):
                            return value
            if (target_object := find_target_object(*values)) is not None:
                if property_name := find_property_name(*values):
                    setattr(target_object, property_name, property_value)
                    return target_object
            return None

        @property
        def option(self):
            return self.startswith("-") if self._argv._fuzzy else self.startswith("--")

        @property
        def empty(self):
            return not self

        @property
        def null(self):
            return self.empty

    def __init__(self, args: Optional[List[str]] = None, fuzzy: bool = True,
                 strip: bool = True, skip: bool = True, delete: bool = False) -> None:
        self._argv = args if isinstance(args, list) and args else (sys.argv[1:] if skip is not False else sys.argv)
        self._argi = 0
        self._fuzzy = fuzzy is not False
        self._strip = strip is not False
        self._delete = delete is True

    @property
    def peek(self) -> Optional[str]:
        return Argv.Arg(self._argv[self._argi], self) if self._argi < len(self._argv) else Argv.Arg(None, self)

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
        return Argv.Arg(arg, self)

    @property
    def value(self):
        return self._argv
