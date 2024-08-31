from typing import Optional, Callable


def print_tree(data: dict,
               indent: Optional[int] = None,
               paths: bool = False,
               path_separator: str = "/",
               obfuscated_value: Optional[str] = None,
               key_modifier: Optional[Callable] = None,
               value_modifier: Optional[Callable] = None,
               value_annotator: Optional[Callable] = None,
               printf: Optional[Callable] = None) -> None:
    """
    Pretty prints the given dictionary. ONLY handles dictionaries
    containing primitive values or other dictionaries recursively.
    """
    if not callable(key_modifier):
        key_modifier = None
    if not callable(value_annotator):
        value_annotator = None
    if not callable(value_modifier):
        value_modifier = None
    if not callable(printf):
        printf = print
    output = (lambda value: printf(f"{' ' * indent}{value}")) if isinstance(indent, int) and indent > 0 else printf
    def traverse(data: dict, indent: str = "", first: bool = False, last: bool = True, path: str = ""):  # noqa
        nonlocal output, paths
        space = "    " if not first else "  "
        for index, key in enumerate(keys := list(data.keys())):
            last = (index == len(keys) - 1)
            corner = "▷ " if first else ("└── " if last else "├── ")
            key_path = f"{path}{path_separator}{key}" if path else key
            if isinstance(value := data[key], dict):
                output(indent + corner + key)
                inner_indent = indent + (space if last else f"{' ' if first else '│'}{space[1:]}")
                traverse(value, indent=inner_indent, last=last, path=key_path)
            else:
                if paths:
                    key = key_path
                key_modification = key_modifier(key_path, key) if key_modifier else key
                value_modification = value_modifier(key_path, value) if value_modifier else key
                value_annotation = value_annotator(key_path) if value_annotator else ""
                if key_modification:
                    key = key_modification
                if value_modification:
                    value = value_modification
                if obfuscated_value:
                    value = obfuscated_value
                key_value = f"{key}: {value}{f' {value_annotation}' if value_annotation else ''}"
                output(indent + corner + key_value)
    traverse(data, first=True)
