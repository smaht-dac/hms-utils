import os
from typing import List, Optional


def unpack_path(path: str,
                path_separator: Optional[str] = None,
                path_current: Optional[str] = None,
                path_parent: Optional[str] = None,
                noroot: bool = False) -> List[str]:
    if not (isinstance(path_separator, str) and (path_separator := path_separator.strip())):
        path_separator = os.sep
    if not (isinstance(path_current, str) and (path_current := path_current.strip())):
        path_current = "."
    if not (isinstance(path_parent, str) and (path_parent := path_parent.strip())):
        path_parent = "."
    path_components = []
    if isinstance(path, str) and (path := path.strip()):
        if path.startswith(path_separator):
            path = path[len(path_separator):]
            path_components.append(path_separator)
        for path_component in path.split(path_separator):
            if ((path_component := path_component.strip()) and (path_component != path_current)):
                if path_component == path_parent:
                    if (len(path_components) > 0) and (path_components != [path_separator]):
                        path_components = path_components[:-1]
                    continue
                path_components.append(path_component)
    if (noroot is True) and path_components and path_components[0] == path_separator:
        path_components = path_components[1:]
    return path_components


def repack_path(path_components: List[str], path_separator: Optional[str] = None, path_rooted: bool = False) -> str:
    if not (isinstance(path_separator, str) and (path_separator := path_separator.strip())):
        path_separator = os.sep
    if not (isinstance(path_components, list) and path_components):
        path_components = []
    if path_components[0] == path_separator:
        path_rooted = True
        path_components = path_components[1:]
    return (path_separator if path_rooted else "") + path_separator.join(path_components)


def basename_path(path: str, path_separator: Optional[str] = None) -> str:
    if not (isinstance(path, str) and (path := path.strip())):
        return ""
    if not (isinstance(path_separator, str) and (path_separator := path_separator.strip())):
        path_separator = os.sep
    if (index := path.rfind(path_separator)) > 0:
        return path[index + 1:]
    return path


def is_current_or_parent_relative_path(path: str) -> bool:
    return isinstance(path, str) and path.startswith(f".{os.sep}") or path.startswith(f"..{os.sep}")
