# TODO: Rewrite/refactor view_portal_object.py

import json
import sys
from typing import Optional
from dcicutils.captured_output import captured_output
from hms_utils.argv import ARGV
from hms_utils.chars import chars
from hms_utils.portal.portal_utils import Portal


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
        ARGV.OPTIONAL(bool): ["--show"],
        ARGV.OPTIONAL(bool): ["--verbose"],
        ARGV.OPTIONAL(bool): ["--debug"],
        ARGV.OPTIONAL(bool): ["--version"],
    })

    _create_portal(env=argv.env, ini=argv.ini, app=argv.app, show=argv.show, verbose=argv.verbose, debug=argv.debug)

    print(json.dumps(argv._dict, indent=4))


def _create_portal(env: Optional[str] = None, ini: Optional[str] = None, app: Optional[str] = None,
                   ping: bool = True, show: bool = False, verbose: bool = False, debug: bool = False) -> Portal:
    portal = None
    with captured_output(not debug):
        try:
            portal = Portal(env, app=app) if env or app else Portal(ini)
        except Exception as e:
            _error(str(e))
    if portal:
        if verbose:
            if portal.env:
                _print(f"Portal environment: {portal.env}")
            if portal.keys_file:
                _print(f"Portal keys file: {portal.keys_file}")
            if portal.key_id:
                if show:
                    _print(f"Portal key: {portal.key_id} {chars.dot} {portal.secret}")
                else:
                    _print(f"Portal key prefix: {portal.key_id[0:2]}******")
            if portal.ini_file:
                _print(f"Portal ini file: {portal.ini_file}")
            if portal.server:
                _print(f"Portal server: {portal.server}")
    if ping:
        if portal.ping():
            _print(f"Portal connectivity: OK {chars.check}")
        else:
            _print(f"Portal connectivity: ERROR {chars.xmark}")
    return portal


def _print(*args, **kwargs) -> None:
    print(*args, **kwargs)


def _error(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr, flush=True)
    sys.exit(1)


if __name__ == "__main__":
    main()
