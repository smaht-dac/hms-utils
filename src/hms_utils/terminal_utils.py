from termcolor import colored


def terminal_color(value: str,
                   color: str,
                   dark: bool = False,
                   bold: bool = False,
                   underline: bool = False,
                   nocolor: bool = False) -> str:
    if nocolor is True:
        return value
    attributes = []
    if dark is True:
        attributes.append("dark")
    if bold is True:
        attributes.append("bold")
    if underline is True:
        attributes.append("underline")
    return colored(value, color.lower(), attrs=attributes)
