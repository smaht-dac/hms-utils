from termcolor import colored


def terminal_color(value: str, color: str, dark: bool = False, bold: bool = False, underline: bool = False) -> str:
    attributes = []
    if dark:
        attributes.append("dark")
    if bold:
        attributes.append("bold")
    if underline:
        attributes.append("underline")
    return colored(value, color.lower(), attrs=attributes)
