from typing import Any, Callable, List, Optional, Tuple, Union
import iterm2
from iterm2.session import Session
from iterm2.connection import Connection
import time


def iterm_run(function: Callable) -> None:
    async def main(connection):
        session = await iterm_init_session(connection)
        await function(session)
    iterm2.run_until_complete(main)


async def iterm_init_session(connection: Connection) -> Session:
    return (await iterm_init(connection))[3]


async def iterm_init(connection: Connection):
    app = await iterm2.async_get_app(connection)
    tab = (window := app.current_window).current_tab
    return app, window, tab, tab.current_session


async def new_pane(session: Session,
                   commands: Union[List[str], str],
                   title: Optional[str] = None,
                   on_output: Optional[Tuple[str, Callable]] = None) -> Session:
    pane = await session.async_split_pane(vertical=False)
    if isinstance(title, str) and title:
        await pane.async_send_text(f"echo -e \"\\033];{title}\007\"\n")
    await pane_output(pane, commands)
    if on_output and len(on_output) > 1:
        await monitor_pane(pane, trigger=on_output[0], callback=on_output[1],
                           data=on_output[3] if len(on_output) > 2 else session)
    return pane


async def pane_output(pane: Session, commands: Union[List[str], str]) -> None:
    if isinstance(commands, str) and commands:
        commands = [commands]
    if isinstance(commands, list):
        for command in commands:
            if command:
                if not command.endswith("\n"):
                    command = command + "\n"
                await pane.async_send_text(command)


async def monitor_pane(pane: Session, trigger: str, callback: Callable, data: Any) -> None:
    line_number = 0
    time.sleep(2)
    while True:
        time.sleep(1)
        lines = [line.string for line in
                 await pane.async_get_contents(first_line=line_number, number_of_lines=25) if line.string]
        line_number += len(lines)
        for line in lines:
            if trigger in line:
                return await callback(data)
