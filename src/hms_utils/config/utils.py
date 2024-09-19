from typing import List, Optional


def unpack_path(path: str, path_separator: Optional[str] = None,
                path_current: Optional[str] = None, path_parent: Optional[str] = None) -> List[str]:
    if not (isinstance(path_separator, str) and (path_separator := path_separator.strip())):
        path_separator = "/"
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
    return path_components


def repack_path(path_components: List[str], root: bool = False, path_separator: Optional[str] = None) -> str:
    if not (isinstance(path_separator, str) and (path_separator := path_separator.strip())):
        path_separator = path_separator
    if not (isinstance(path_components, list) and path_components):
        path_components = []
    if path_components[0] == path_separator:
        root = True
        path_components = path_components[1:]
    return (path_separator if root else "") + path_separator.join(path_components)
