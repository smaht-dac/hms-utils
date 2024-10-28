# TODO: Rewrite/refactor view_portal_object.py

from typing import Optional
from dcicutils.captured_output import captured_output
from hms_utils.portal_utils import Portal
from hms_utils.argv import ARGV  # noqa


def main():

    argv = ARGV({
        ARGV.REQUIRED(str): ["uuid"],
        ARGV.OPTIONAL(str): ["--app"],
        ARGV.OPTIONAL(str): ["--env", "--e"],
        ARGV.OPTIONAL(str): ["--ini", "--ini-file"],
        ARGV.OPTIONAL(bool): ["--inserts"],
        ARGV.OPTIONAL(bool): ["--insert-files"],
        ARGV.OPTIONAL(bool): ["--output", "--out"],
        ARGV.OPTIONAL(bool): ["--raw"],
        ARGV.OPTIONAL(bool): ["--database"],
        ARGV.OPTIONAL(bool): ["--yaml", "--yml"],
        ARGV.OPTIONAL(bool): ["--refs", "--ref"],
        ARGV.OPTIONAL(bool): ["--verbose"],
        ARGV.OPTIONAL(bool): ["--debug"],
        ARGV.OPTIONAL(bool): ["--version"],
    })

    print(argv)


def _create_portal(ini: str, env: Optional[str] = None,
                   server: Optional[str] = None, app: Optional[str] = None,
                   verbose: bool = False, debug: bool = False) -> Portal:
    portal = None
    with captured_output(not debug):
        portal = Portal(env, server=server, app=app) if env or app else Portal(ini)
    if portal:
        if verbose:
            if portal.env:
                _print(f"Portal environment: {portal.env}")
            if portal.keys_file:
                _print(f"Portal keys file: {portal.keys_file}")
            if portal.key_id:
                _print(f"Portal key prefix: {portal.key_id[0:2]}******")
            if portal.ini_file:
                _print(f"Portal ini file: {portal.ini_file}")
            if portal.server:
                _print(f"Portal server: {portal.server}")
        return portal


def _print(*args, **kwargs) -> None:
    print(*args, **kwargs)


if __name__ == "__main__":
    main()
