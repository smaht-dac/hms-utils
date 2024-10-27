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
    _RULE_DELIMITER = ":"
    _RULE_PREFIX = f"__rule__{_RULE_DELIMITER}"
    _RULE_PREFIX_LEN = len(_RULE_PREFIX)

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
            if self._argv._escaping:
                return False
            return self._argv._is_option_any_of(self, options)

        def set_value_boolean(self, option: Argv._Option) -> bool:
            if isinstance(option, str): option = Argv._Option(option)  # noqa
            if self.is_any_of(option._options):
                setattr(self._argv._values, option._property_name, True)
                return True
            return False

        def set_value_string(self, option: Argv._Option) -> bool:
            return self._set_value_property(option)

        def set_value_strings(self, option: Argv._Option) -> bool:
            return self._set_value_properties(option)

        def set_value_integer(self, option: Argv._Option) -> bool:
            return self._set_value_property(option, convert=to_integer)

        def set_value_integers(self, option: Argv._Option) -> bool:
            return self._set_value_properties(option, convert=to_integer)

        def set_value_float(self, option: Argv._Option) -> bool:
            return self._set_value_property(option, convert=to_float)

        def set_value_floats(self, option: Argv._Option) -> bool:
            return self._set_value_properties(option, convert=to_float)

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
            if self.is_any_of(option._options) and (not hasattr(self._argv._values, option._property_name)):
                if (value := self._argv._peek).is_not_null and ((value != Argv._ESCAPE_VALUE) or (not value.is_option)):
                    if value == Argv._ESCAPE_VALUE:
                        if (value := self._argv._next).is_null:
                            return False
                    if (not callable(convert)) or ((value := convert(value)) is not None):
                        setattr(self._argv._values, option._property_name, value if callable(convert) else str(value))
                        self._argv._next
                        return True
            return False

        def _set_value_properties(self, option: Union[Argv._Option, str], convert: Optional[Callable] = None) -> bool:
            if isinstance(option, str): option = Argv._Option(option)  # noqa
            if not callable(convert):
                convert = lambda value: str(value)  # noqa
            if self.is_any_of(option._options):
                values = []
                if (value := getattr(self._argv._values, option._property_name, None)) is not None:
                    if isinstance(value, list):
                        values[:0] = value
                    elif (value := convert(value)) is not None:
                        values.append(value)
                setattr(self._argv._values, option._property_name, values)
                while True:
                    if (value := self._argv._peek).is_null or value.is_option:
                        break
                    if ((value == Argv._ESCAPE_VALUE) and (value := self._argv._next).is_null) or value.is_option:
                        break
                    if (value := convert(value)) is None:
                        break
                    values.append(value)
                    self._argv._next
                return True
            return False

        def _set_default_value_property(self, option: Argv._Option, convert: Optional[Callable] = None) -> bool:
            if self and (not self.is_option):
                if (value := self) == Argv._ESCAPE_VALUE:
                    if (value := argv._argv._next).is_null:
                        return False
                for option in option._options:
                    if (not callable(convert)) or ((value := convert(value)) is not None):
                        if not hasattr(self._argv._values, option):
                            setattr(self._argv._values, option, value)
                            return True
            return False

        def _set_default_value_properties(self, option: Argv._Option, convert: Optional[Callable] = None) -> bool:
            parsed = False ; value = self  # noqa
            for option in option._options:
                option_values = getattr(self._argv._values, option, None)
                while True:
                    if value.is_null:
                        break
                    if ((value == Argv._ESCAPE_VALUE) and (value := self._argv._next).is_null) or value.is_option:
                        break
                    if callable(convert) and ((value := convert(value)) is None):
                        break
                    if option_values is None:
                        option_values = []
                        setattr(self._argv._values, option, option_values)
                    option_values.append(value if callable(convert) else str(value))
                    parsed = True
                    if (value := self._argv._peek).is_null or value.is_option:
                        break
                    self._argv._next
            return parsed

    class _Values:
        pass

    class _OptionDefinitions:
        def __init__(self, fuzzy: bool = True) -> None:
            self._definitions = []
            self._fuzzy = fuzzy is not False
            self._rule_exactly_one_of = []
            self._rule_at_least_one_of = []
            self._rule_at_most_one_of = []
            self._rule_depends_on = []
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

        def add_rule_exactly_one_of(self, options: List[str]) -> None:
            if options := list(set(to_non_empty_string_list(options))):
                self._rule_exactly_one_of.append(options)

        def add_rule_at_least_one_of(self, options: List[str]) -> None:
            if options := list(set(to_non_empty_string_list(options))):
                self._rule_at_least_one_of.append(options)

        def add_rule_at_most_one_of(self, options: List[str]) -> None:
            if options := list(set(to_non_empty_string_list(options))):
                self._rule_at_most_one_of.append(options)

        def add_rule_depends_on(self, options: List[str]) -> None:
            dependent_options = [] ; required_options = []  # noqa
            if options := to_non_empty_string_list(options):
                for optioni in range(len(options)):
                    if options[optioni].startswith(f"{Argv._RULE_PREFIX}depends_on"):
                        if dependent_options := options[:optioni]:
                            if (optioni + 1) < len(options):
                                if required_options := options[optioni + 1:]:
                                    self._rule_depends_on.append({"depends": dependent_options, "on": required_options})
                                    return

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

        def __eq__(self, other):
            return id(self) == id(other)

        def __hash__(self):
            return hash(id(self))

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
        if (parse is True) and self._option_definitions._definitions:
            self.parse()

    @property
    def list(self) -> List[str]:
        return self._argv

    @property
    def values(self) -> Argv._Values:
        return self._values

    def parse(self, *args, skip: bool = True, report: bool = True,
              exit: Optional[bool] = None, printf: Optional[Callable] = None) -> List[str]:

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

        if not self._option_definitions:
            return []

        errors = []
        missing_options = []
        unparsed_args = []
        rule_violations_exactly_one_of_missing = []
        rule_violations_exactly_one_of_toomany = []
        rule_violations_at_least_one_of_missing = []
        rule_violations_at_most_one_of_toomany = []
        rule_violations_depends_on = []

        for arg in self:
            parsed = False
            for option in self._option_definitions._definitions:
                if option._action(arg, option):
                    parsed = True
                    break
            if not parsed:
                unparsed_args.append(arg)

        defined_value_options = set(self._defined_value_options())

        for rule_options in self._option_definitions._rule_exactly_one_of:
            if rule_options := set(self._find_options(rule_options)):
                if len(intersection_options := rule_options & defined_value_options) == 0:
                    # Exactly one of the specifed rule options should be specified but none are.
                    rule_violations_exactly_one_of_missing.append(
                        [option._option_name for option in rule_options])
                elif len(intersection_options) != 1:
                    # Exactly one of the specifed rule options should be specified more than one are.
                    rule_violations_exactly_one_of_toomany.append(
                        [option._option_name for option in rule_options])

        for rule_options in self._option_definitions._rule_at_least_one_of:
            if rule_options := set(self._find_options(rule_options)):
                intersection_options = rule_options & defined_value_options
                if len(intersection_options) == 0:
                    # At least one of the specifed rule options should be specified but none are.
                    rule_violations_at_least_one_of_missing.append(
                        [option._option_name for option in rule_options])

        for rule_options in self._option_definitions._rule_at_most_one_of:
            if rule_options := set(self._find_options(rule_options)):
                intersection_options = rule_options & defined_value_options
                if len(intersection_options) > 0:
                    # At most one of the specifed rule options should be specified but more than one are.
                    rule_violations_at_most_one_of_toomany.append(
                        [option._option_name for option in rule_options])

        for rule in self._option_definitions._rule_depends_on:
            rule_dependent_options = to_non_empty_string_list(rule.get("depends"))
            rule_required_options = to_non_empty_string_list(rule.get("on"))
            rule_dependent_options = self._find_options(rule_dependent_options)
            rule_required_options = self._find_options(rule_required_options)
            for rule_dependent_option in rule_dependent_options:
                if hasattr(self._values, rule_dependent_option._property_name):
                    for rule_required_option in rule_required_options:
                        if not hasattr(self._values, rule_required_option._property_name):
                            rule_violations_depends_on.append([rule_dependent_option._option_name,
                                                               rule_required_option._option_name])

        # Define value properties as None for any options/properties not specified; must be after above.
        for option in self._option_definitions._definitions:
            if not hasattr(self._values, option._property_name):
                if option._required:
                    if option._option_name not in missing_options:
                        missing_options.append(option._option_name)
                setattr(self._values, option._property_name, None)

        if unparsed_args:
            errors.append(f"Unrecognized argument"
                          f"{'s' if len(unparsed_args) > 1 else ''}: {', '.join(unparsed_args)}")
        if missing_options:
            errors.append(f"Missing required option"
                          f"{'s' if len(missing_options) > 1 else ''}: {', '.join(missing_options)}")
        for violation in rule_violations_exactly_one_of_toomany:
            errors.append(f"Exactly one of these options may be specified: {', '.join(violation)}")
        for violation in rule_violations_exactly_one_of_missing:
            errors.append(f"Exactly one of these options must be specified: {', '.join(violation)}")
        for violation in rule_violations_at_least_one_of_missing:
            errors.append(f"At least one of these options must be specified: {', '.join(violation)}")
        for violation in rule_violations_at_most_one_of_toomany:
            errors.append(f"At most one of these options must be specified: {', '.join(violation)}")
        for violation in rule_violations_depends_on:
            errors.append(f"Option {violation[0]} depends on option: {violation[1]}")

        if (report is not False) and errors:
            if not callable(printf):
                printf = lambda *args, **kwargs: print(*args, **kwargs, file=sys.stderr)  # noqa
            for error in errors:
                printf(error)
            if exit is True:
                sys.exit(1)

        return errors

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
                    if (option_type.startswith(Argv._RULE_PREFIX) and
                        (option_type := option_type[Argv._RULE_PREFIX_LEN:]) and
                        ((index := option_type.find(Argv._RULE_DELIMITER)) > 0) and
                        (option_type := option_type[:index])):  # noqa
                        if option_type == "exactly_one_of":
                            option_definitions.add_rule_exactly_one_of(option_options)
                            continue
                        elif option_type == "at_least_one_of":
                            option_definitions.add_rule_at_least_one_of(option_options)
                            continue
                        elif option_type == "at_most_one_of":
                            option_definitions.add_rule_at_most_one_of(option_options)
                            continue
                        elif option_type == "depends_on":
                            option_definitions.add_rule_depends_on(option_options)
                            continue
                        option_type = to_integer(option_type[0:index])
                    elif (index := option_type.find(Argv._RULE_DELIMITER)) > 1:
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

    def _defined_value_options(self) -> List[Argv._Option]:
        defined_value_options = []
        for option in self._option_definitions._definitions:
            if hasattr(self._values, option._property_name):
                defined_value_options.append(option)
        return defined_value_options

    def _find_options(self, options: Union[List[str], str]) -> List[Argv._Option]:
        found_options = []
        if options := to_non_empty_string_list(options):
            for option_definition in self._option_definitions._definitions:
                for option_definition_option in option_definition._options:
                    if self._is_option_any_of(option_definition_option, options):
                        found_options.append(option_definition)
                        break
        return found_options

    def _is_option(self, value: str) -> bool:
        if self._escaping:
            return False
        if isinstance(value, str) and (value := value.strip()):
            if value.startswith(Argv._OPTION_PREFIX) and (value := value[Argv._OPTION_PREFIX_LEN:].strip()):
                return True
            elif self._fuzzy:
                if value.startswith(Argv._FUZZY_OPTION_PREFIX) and value[Argv._FUZZY_OPTION_PREFIX_LEN:].strip():
                    return True
        return False

    def _is_option_any_of(self, value: str, options: List[str]) -> bool:
        def match(value: str, option: str) -> bool:
            if (isinstance(option, str) and (option := option.strip()) and
                isinstance(value, str) and (value := value.strip())):  # noqa
                if value == option:
                    return True
                elif self._fuzzy:
                    if (option.startswith(Argv._OPTION_PREFIX) and
                        (value == Argv._FUZZY_OPTION_PREFIX + option[Argv._OPTION_PREFIX_LEN:])):  # noqa
                        return True
                    elif (value.startswith(Argv._OPTION_PREFIX) and
                          (option == Argv._FUZZY_OPTION_PREFIX + value[Argv._OPTION_PREFIX_LEN:])):
                        return True
            return False
        return any(match(value, option) for option in options) if isinstance(options, list) else False

    @staticmethod
    def _is_option_type(option_type: Any) -> bool:
        if isinstance(option_type, int):
            return (((Argv.BOOLEAN | Argv.DEFAULT | Argv.DEFAULTS |
                      Argv.FLOAT | Argv.FLOATS | Argv.INTEGER | Argv.INTEGERS |
                      Argv.STRING | Argv.STRINGS | Argv.OPTIONAL | Argv.REQUIRED) & option_type) == option_type)
        return False

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
            if (not self._escaping) and (value == Argv._ESCAPE_VALUE):
                self._escaping = True
                return self._next
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
        return str(option_type) + Argv._RULE_DELIMITER + str(uuid())

    @staticmethod
    def REQUIRED(type: Optional[Type[Union[str, int, float, bool]]] = None):
        return ARGV.OPTIONAL(type=type, _required=True)

    @classmethod
    @property
    def EXACTLY_ONE_OF(cls):
        return f"{Argv._RULE_PREFIX}exactly_one_of{Argv._RULE_DELIMITER}{str(uuid())}"

    @classmethod
    @property
    def AT_LEAST_ONE_OF(cls):
        return f"{Argv._RULE_PREFIX}at_least_one_of{Argv._RULE_DELIMITER}{str(uuid())}"

    @classmethod
    @property
    def AT_MOST_ONE_OF(cls):
        return f"{Argv._RULE_PREFIX}at_most_one_of{Argv._RULE_DELIMITER}{str(uuid())}"

    @classmethod
    @property
    def DEPENDENCY(cls, *args):
        return f"{Argv._RULE_PREFIX}depends_on:{str(uuid())}"

    @classmethod
    @property
    def DEPENDS_ON(cls, *args):
        return f"{Argv._RULE_PREFIX}depends_on:{str(uuid())}"

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
    errors = args.parse(["--config", "abc", "ghi", "-xyz",
                         "--config", "foo", "--import-file", "secrets.json",
                         "-count", "123", "456", "-key", "321", "2342.234",
                         "-124", "somefile.json", "some-other"])

    assert args.config == ["abc", "ghi", "foo"]
    assert args.count == [123, 456]
    assert args.import_file == "secrets.json"
    assert args.key == [321, 2342.234]
    assert args.others == "somefile.json", "some-other"
    assert errors[0] == "Unrecognized arguments: -xyz, -124, some-other"
    assert errors[1] == "Missing required options: --foo, goo"

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
    errors = argv.parse(["foo", "bara", "barb", "-xyz", "goo",
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
    assert argv.config == ["configfile"]

    assert errors[0] == "Unrecognized argument: -xyz"
    assert errors[1] == "Missing required options: --merge, --formatted"

if True:
    argv = Argv(
        Argv.DEFAULTS | Argv.FLOAT, "floats", "reals"
    )
    argv.parse(["12", "34", "56", "1.2", "3.4"])
    assert argv.floats == [12, 34, 56, 1.2, 3.4]

if True:
    argv = Argv(
        Argv.DEFAULT | Argv.INTEGER, "max",
        Argv.DEFAULTS | Argv.FLOAT, "floats", "reals"
    )
    argv.parse(["12", "34", "56", "1.2", "3.4"])
    assert argv.max == 12
    assert argv.floats == [34, 56, 1.2, 3.4]


if True:
    argv = Argv(
        Argv.STRING, ("--password", "--passwd")
    )
    argv.parse(["foo", "bara", "barb", "-xyz", "goo", "-passwd", "pas"])
    assert argv.password == "pas"

if True:
    argv = Argv(
        Argv.STRING, ["--password"],
        Argv.DEFAULTS, "file"
    )
    argv.parse(["foo", "--password", "pas"])
    assert argv.password == "pas"

if True:
    argv = Argv(
        Argv.STRING, ["--password"],
        Argv.DEFAULTS, ("thedefaults"), strip=False)
    argv.parse(["foo", "bar", "--password", "pas", " argwithspace ", "", ""])
    assert argv.password == "pas"
    assert argv.thedefaults == ["foo", "bar", " argwithspace ", "", ""]

if True:
    argv = Argv({
        Argv.STRING: ["--password"],
        Argv.DEFAULTS: "thedefaults",
    })
    argv.parse(["foo", "bar", "--password", "pas", " argwithspace ", "", ""])
    assert argv.password == "pas"
    assert argv.thedefaults == ["foo", "bar", "argwithspace", "", ""]

if True:
    argv = Argv({
        Argv.STRING: ["--password"],
        Argv.REQUIRED: "--req",
        Argv.DEFAULTS: "thedefaults",
    })
    argv.parse(["foo", "bar", "--password", "pas", " argwithspace ", "", "", "--req", "xyz"])
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
    errors = argv.parse(["foo", "bar", "-password", "pas", " argwithspace ", "", "", "-reqx", "xyz"])
    assert argv.password == "pas"
    print(argv.thedefaults)
    assert argv.thedefaults == ["foo", "bar", "argwithspace", "", "", "xyz"]
    assert argv.req is True
    assert argv.values.xpassword is None
    errors == ["Missing required option: --maxn"]


if True:
    argv = ARGV({
        ARGV.OPTIONAL(str): ["--encrypt"],
        ARGV.OPTIONAL(str): ["--decrypt"],
        ARGV.OPTIONAL(str): ["--output", "--out"],
        ARGV.OPTIONAL(bool): ["--yes", "--force"],
        ARGV.OPTIONAL(bool): ["--verbose"],
        ARGV.OPTIONAL(bool): ["--debug"],
        ARGV.OPTIONAL(str): ["--password", "--passwd"]
    })
    errors = argv.parse(["--encrypt", "somefile", "--encrypt", "anotherfile"], report=False)
    assert errors == ["Unrecognized arguments: --encrypt, anotherfile"]
    assert argv.encrypt == "somefile"
    assert argv.decrypt is None

if True:
    argv = ARGV({
        ARGV.OPTIONAL(bool): ["--encrypt"],
        ARGV.OPTIONAL(bool): ["--decrypt"],
        ARGV.OPTIONAL(str): ["--output", "--out"],
        ARGV.OPTIONAL(str): ["--destination", "--dest"],
        ARGV.OPTIONAL(bool): ["-yes", "--y", "--force"],
        ARGV.OPTIONAL(bool): ["--verbose"],
        ARGV.OPTIONAL(bool): ["--debug"],
        ARGV.OPTIONAL(str): ["--password", "--passwd"],
        ARGV.REQUIRED(str): ["file"],
        ARGV.OPTIONAL(bool): ["--formatted"],
        ARGV.OPTIONAL(bool): ["--json"],
        ARGV.EXACTLY_ONE_OF: ["--encrypt", "--decrypt"],
        ARGV.EXACTLY_ONE_OF: ["--output", "-yes"],
        ARGV.DEPENDENCY: ["--formatted", ARGV.DEPENDS_ON, "-json"]
    })
    errors = argv.parse(["--encrypt", "--decrypt", "somefile", "--formatted", "--dest", "--", "-destfile"])
    assert errors == ["Exactly one of these options may be specified: --encrypt, --decrypt",
                      "Exactly one of these options must be specified: --output, -yes",
                      "Option --formatted depends on option: --json"]
    assert argv.destination == "-destfile"
