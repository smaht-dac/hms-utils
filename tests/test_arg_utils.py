from hms_utils.arg_utils import Argv


def test_argv_a():
    argv = Argv(["dummyt.py", "abc", "def", "--config", "file.json",
                 "--verbose", "-debug", "--configs", "ghi.json", "jkl.json", "mno.json"])
    for arg in argv:
        if arg.set_string("--config"):
            continue
        if arg.set_boolean("--debug"):
            continue
        if arg.set_boolean("--verbose"):
            continue
        if arg.set_string_multiple("--configs"):
            continue
    assert argv.values.config == "file.json"
    assert argv.values.verbose is True
    assert argv.values.debug is True
    assert argv.values.configs == ["ghi.json", "jkl.json", "mno.json"]


def test_argv_b():
    args = ["dummyt.py", "abc", "def", "--config", "file.json",
            "--verbose", "-debug", "--configs", "ghi.json", "jkl.json", "mno.json"]
    argv = Argv(args, delete=True)
    argv.process(
        "--config", "-file", Argv.STRING,
        "--configs", Argv.STRINGS,
        "--verbose", Argv.BOOLEAN,
        "--debug", Argv.BOOLEAN
    )
    assert argv.values.verbose is True
    assert argv.values.debug is True
    assert argv.values.config == "file.json"
    assert argv.values.configs == ["ghi.json", "jkl.json", "mno.json"]

    return
    args = ["dummyt.py", "abc", "def", "--config", "file.json",
            "--verbose", "-debug", "--configs", "ghi.json", "jkl.json", "mno.json"]
    argv = Argv(args)
    argv.process(
        Argv.STRING, "--config", "-file",
        Argv.STRINGS, "--configs",
        Argv.BOOLEAN, "--verbose",
        Argv.BOOLEAN, "--debug"
    )
    import pdb ; pdb.set_trace()  # noqa
    pass
    assert argv.values.verbose is True
    assert argv.values.debug is True
    assert argv.values.config == "file.json"
    assert argv.values.configs == ["ghi.json", "jkl.json", "mno.json"]
