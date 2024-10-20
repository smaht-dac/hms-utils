from hms_utils.arg_utils import Argv


def test_argv_a():

    expected = [{"action": Argv._Arg.set_string, "options": ["--abc", "-def"]},
                {"action": Argv._Arg.set_boolean, "options": ["--ghi"]}]

    definitions = [Argv.STRING, "--abc", "-def", Argv.BOOLEAN, "--ghi"]
    assert Argv._process_definitions(definitions) == expected

    definitions = ["--abc", "-def", Argv.STRING, "--ghi", Argv.BOOLEAN]
    assert Argv._process_definitions(definitions) == expected


def test_argv_b():
    argv = Argv(["dummyt.py", "abc", "def", "--config", "file.json",
                 "--verbose", "-debug", "--configs", "ghi.json", "jkl.json", "mno.json"])
    for arg in argv:
        if arg.set_string("--config"):
            continue
        if arg.set_boolean("--debug"):
            continue
        if arg.set_boolean("--verbose"):
            continue
        if arg.set_strings("--configs"):
            continue
    assert argv.values.config == "file.json"
    assert argv.values.verbose is True
    assert argv.values.debug is True
    assert argv.values.configs == ["ghi.json", "jkl.json", "mno.json"]


def test_argv_c():
    args = ["abc", "def", "--config", "file.json", "--verbose",
            "-debug", "--configs", "ghi.json", "jkl.json", "mno.json"]
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

    args = ["abc", "def", "--config", "file.json", "--verbose",
            "-debug", "--configs", "ghi.json", "jkl.json", "mno.json"]
    argv = Argv(
        Argv.STRING, "--config", "-file",
        Argv.STRINGS, "--configs",
        Argv.BOOLEAN, "--verbose",
        Argv.BOOLEAN, "--debug"
    )
    argv.process(args)
    assert argv.values.verbose is True
    assert argv.values.debug is True
    assert argv.values.config == "file.json"
    assert argv.values.configs == ["ghi.json", "jkl.json", "mno.json"]
