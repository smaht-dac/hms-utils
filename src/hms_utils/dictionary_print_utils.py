from __future__ import annotations
from prettytable import PrettyTable
from typing import Callable, Optional
from hms_utils.chars import chars
from hms_utils.dictionary_parented import JSON


def print_dictionary_tree(data: dict,
                          indent: Optional[int] = None,
                          paths: bool = False,
                          path_separator: str = "/",
                          root_indicator: Optional[Callable] = None,
                          parent_annotator: Optional[Callable] = None,
                          value_annotator: Optional[Callable] = None,
                          key_modifier: Optional[Callable] = None,
                          value_modifier: Optional[Callable] = None,
                          arrow_indicator: Optional[Callable] = None,
                          printf: Optional[Callable] = None,
                          debug: bool = False) -> None:
    """
    Pretty prints the given dictionary. ONLY handles dictionaries
    containing primitive values or other dictionaries recursively.
    """
    if not callable(root_indicator):
        root_indicator = None
    if not callable(parent_annotator):
        parent_annotator = None
    if not callable(value_annotator):
        value_annotator = None
    if not callable(key_modifier):
        key_modifier = None
    if not callable(value_modifier):
        value_modifier = None
    if not callable(arrow_indicator):
        arrow_indicator = None
    if not callable(printf):
        printf = print
    if not isinstance(indent, int):
        indent = 0
    output = (lambda value: printf(f"{' ' * indent}{value}")) if indent > 0 else printf
    def traverse(data: dict, indent: str = "", first: bool = False, last: bool = True, path: str = ""):  # noqa
        if not path:
            if isinstance(data, JSON):
                path = data.path
        nonlocal output, paths, key_modifier, value_annotator, value_modifier
        space = "    " if not first else "  "
        for index, key in enumerate(keys := list(data.keys())):
            last = (index == len(keys) - 1)
            corner = "▷" if first else ("└──" if last else "├──")
            if isinstance(data, JSON):
                key_path = data.context_path(path_separator=path_separator, path_suffix=key, path_rooted=True)
            else:
                key_path = f"{path}{path_separator}{key}" if path else key
            # key_path = f"{path}{path_separator}{key}" if path else key
            if isinstance(value := data[key], dict):
                if (debug is True) and isinstance(value, JSON):
                    key += f" {chars.dot} id: {id(value)}"
                    if parent := value.parent:
                        key += f" {chars.dot} parent: {id(parent)}"
                if parent_annotator and (parent_annotation := parent_annotator(value)):
                    key = key + parent_annotation
                output(indent + corner + " " + key)
                inner_indent = indent + (space if last else f"{' ' if first else '│'}{space[1:]}")
                traverse(value, indent=inner_indent, last=last, path=key_path)
            elif isinstance(value, list):
                output(indent + corner + " " + key)
                inner_indent = (indent if first else indent + (2 * " ")) + (2 * " ")
                for element_index, element_value in enumerate(value):
                    if isinstance(element_value, dict):
                        element_output_value = "{}"
                        if parent_annotator and (parent_annotation := parent_annotator(element_value)):
                            element_output_value += parent_annotation
                        output(f"{inner_indent}└── [{element_index}]: {element_output_value}")
                        traverse(element_value, indent=inner_indent + (9 * " "))
                    else:
                        output(f"{inner_indent}└── [{element_index}]: {element_value}")
            else:
                if paths:
                    key = key_path
                key_modification = key_modifier(key_path, key) if key_modifier else key
                value_modification = value_modifier(key_path, value) if value_modifier else value
                value_annotation = value_annotator(data, key, value) if value_annotator else ""
                arrow_indication = arrow_indicator(key_path, value) if arrow_indicator else ""
                if key_modification:
                    key = key_modification
                if value_modification:
                    value = value_modification
                if arrow_indication:
                    corner = corner[:-1] + arrow_indication
                if (debug is True) and isinstance(data, JSON):
                    if not value_annotation:
                        value_annotation = ""
                    value_annotation += f" {chars.dot} parent: {id(data)}"
                output(f"{indent}{corner} {key}: {value}{f'{value_annotation}' if value_annotation else ''}")
    if root_indicator:
        if isinstance(root_indication := root_indicator(), str) and root_indication:
            output(root_indication)
    traverse(data, first=True)


def print_dictionary_list(data: dict,
                          path_separator: str = "/",
                          prefix: Optional[str] = None,
                          key_modifier: Optional[Callable] = None,
                          value_modifier: Optional[Callable] = None,
                          value_annotator: Optional[Callable] = None) -> None:
    if not callable(key_modifier):
        key_modifier = None
    if not callable(value_annotator):
        value_annotator = None
    if not callable(value_modifier):
        value_modifier = None
    if not isinstance(prefix, str):
        prefix = ""
    def traverse(data: dict, path: str = "") -> None:  # noqa
        nonlocal path_separator, key_modifier, value_annotator, value_modifier
        for key in data:
            key_path = f"{path}{path_separator}{key}" if path else key
            if isinstance(item := data[key], dict):
                traverse(item, path=key_path)
            else:
                value = str(item)
                key_modification = key_modifier(key_path) if key_modifier else key_path
                value_modification = value_modifier(key_path, value) if value_modifier else value
                value_annotation = value_annotator(key_path) if value_annotator else ""
                if key_modification:
                    key = key_modification
                if value_modification:
                    value = value_modification
                print(f"{prefix}{key}: {value}{f' {value_annotation}' if value_annotation else ''}")
    traverse(data)


def print_dictionary_as_table(header_name: str, header_value: str,
                              dictionary: dict, display_value: Callable, sort: bool = True) -> None:
    table = PrettyTable()
    table.field_names = [header_name, header_value]
    table.align[header_name] = "l"
    table.align[header_value] = "l"
    if not callable(display_value):
        display_value = lambda _, value: value  # noqa
    for key_name, key_value in sorted(dictionary.items(), key=lambda item: item[0]) if sort else dictionary.items():
        table.add_row([key_name, display_value(key_name, key_value)])
    print(table)
