from typing import Optional, Callable


def print_tree(data: dict,
               indent: Optional[int] = None,
               paths: bool = False,
               path_separator: str = "/",
               obfuscated_value: Optional[str] = None,
               annotator: Optional[Callable] = None,
               printf: Optional[Callable] = None) -> None:
    """
    Pretty prints the given dictionary. ONLY handles dictionaries
    containing primitive values or other dictionaries recursively.
    """
    if not callable(annotator):
        annotator = None
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
                output(indent + corner + str(key))
                inner_indent = indent + (space if last else f"{' ' if first else '│'}{space[1:]}")
                traverse(value, indent=inner_indent, last=last, path=key_path)
            else:
                annotation = annotator(key_path) if annotator else ""
                if paths:
                    key = key_path
                if obfuscated_value:
                    output(indent + corner + f"{key}: {obfuscated_value}{f' {annotation}' if annotation else ''}")
                else:
                    output(indent + corner + f"{key}: {value}{f' {annotation}' if annotation else ''}")
    traverse(data, first=True)
