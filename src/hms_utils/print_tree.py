from typing import Optional, Callable


def print_tree(data: dict, indent: Optional[int] = None, printf: Optional[Callable] = None) -> None:
    if not callable(printf):
        printf = print
    output = (lambda value: printf(f"{' ' * indent}{value}")) if isinstance(indent, int) and indent > 0 else printf
    def traverse(data: dict, indent: str = "", first: bool = False, last: bool = True):  # noqa
        nonlocal output
        space = "    " if not first else "  "
        for index, key in enumerate(keys := list(data.keys())):
            last = (index == len(keys) - 1)
            corner = "▷ " if first else ("└── " if last else "├── ")
            if isinstance(value := data[key], dict):
                output(indent + corner + str(key))
                traverse(value, indent=indent + (space if last else f"{' ' if first else '│'}{space[1:]}"), last=last)
            else:
                output(indent + corner + f"{key}: {value}")
    traverse(data, first=True)
