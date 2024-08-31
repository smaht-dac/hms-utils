import iterm2
import datetime


# This function gets called once per second.
@iterm2.StatusBarRPC
async def coro(knobs):
    return datetime.datetime.now(datetime.timezone.utc).strftime("UTC:%H:%M:%S")


def iterm_run() -> None:
    async def main(connection):
        component = iterm2.StatusBarComponent(
            short_description="UTC Clock",
            detailed_description="Shows the time in jolly old England",
            knobs=[],
            exemplar="UTC: 12:00",
            update_cadence=1,
            identifier="com.iterm2.example.utc-clock")
        await component.async_register(connection, coro)
    iterm2.run_forever(main)


iterm_run()
