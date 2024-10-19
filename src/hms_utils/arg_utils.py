from __future__ import annotations
import sys
from typing import Any, List, Optional


class Args:
    class Arg(str):  # noqa
        def __new__(cls, value: str, args: Args) -> None:
            value = (value.strip() if args._strip else value) if isinstance(value, str) else ""
            value = super().__new__(cls, value)
            value._args = args
            return value
        def anyof(self, *values) -> bool:  # noqa
            def match(value: Any) -> bool:
                nonlocal self
                return (isinstance(value, str) and
                        ((self == value) or (self._args._fuzzy and value.startswith("--") and (self == value[1:]))))
            for value in values:
                if isinstance(value, list):
                    for element in value:
                        if match(value):
                            return True
                elif match(value):
                    return True
            return False
        @property  # noqa
        def option(self):
            return self.startswith("-") if self._args._fuzzy else self.startswith("--")
        @property  # noqa
        def empty(self):
            return not self
        @property  # noqa
        def null(self):
            return self.empty
    def __init__(self, args: Optional[List[str]] = None, fuzzy: bool = True, strip: bool = True, skip: bool = True):  # noqa
        self._args = args if isinstance(args, list) and args else (sys.argv[1:] if skip is not False else sys.argv)
        self._argi = 0
        self._fuzzy = fuzzy is not False
        self._strip = strip is not False
    @property  # noqa
    def peek(self) -> Optional[str]:
        return Args.Arg(self._args[self._argi], self) if self._argi < len(self._args) else Args.Arg(None, self)
    @property  # noqa
    def next(self) -> Optional[str]:
        if (value := self.peek) is not None:
            self._argi += 1
            return value
        return None
    def __iter__(self) -> Args:  # noqa
        return self
    def __next__(self) -> Optional[str]:  # noqa
        if self._argi >= len(self._args):
            raise StopIteration
        arg = self._args[self._argi]
        self._argi += 1
        return Args.Arg(arg, self)
    @property  # noqa
    def value(self):
        return self._args
