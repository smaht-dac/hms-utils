from importlib.metadata import version as get_package_version


def get_version(package_name: str = "hms-utils") -> str:
    try:
        return get_package_version(package_name)
    except Exception:
        return ""
