from hms_utils.json_utils import JSON
from hms_utils.dictionary_utils import sort_dictionary


def test_json_utils():

    data = {
        "alfa": "alfa_value",
        "bravo": {
            "charlie": "charlie_value",
            "delta": {
                "echo": {
                    "foxtrot": 123
                }
             },
            "golf": {
                "hotel": {
                    "indigo": "indigo_value"
                }
            }
        }
    }

    def assert_some_basic_truths(json):

        nonlocal data

        assert json["alfa"] == data["alfa"]
        assert json == data
        assert json["alfa"] == data["alfa"]
        assert json["bravo"]["delta"] == data["bravo"]["delta"]
        assert json.parent is None
        assert json["bravo"].parent == json
        assert id(json["bravo"].parent) == id(json)
        assert id(json["bravo"]["delta"].parent) == id(json["bravo"])
        assert id(json["bravo"]["delta"].parent) == id(json["bravo"]["golf"].parent)
        assert id(json["bravo"]["delta"].parent) == id(json["bravo"]["golf"]["hotel"].parent.parent)
        assert id(json["bravo"]["delta"].root) == id(json)
        assert json.root == json and id(json.root) == id(json)
        assert json["bravo"]["golf"]["hotel"].context_path == ["bravo", "golf", "hotel"]

    json = JSON(data)
    assert_some_basic_truths(json)

    jsonx = JSON(json)
    assert_some_basic_truths(jsonx)
    assert jsonx == json
    assert id(jsonx) != id(json)

    expected_output = [
        "alfa",
        "alfa_value",
        str(data),
        "bravo",
        str(data["bravo"]),
    ]

    output = []
    json = JSON(data)
    for key in json:
        value = json[key]
        if isinstance(value, dict):
            output.append(str(value.parent))
        output.append(str(key))
        output.append(str(value))
    assert output == expected_output

    output = []
    json = JSON(data)
    for key, value in json.items():
        value = json[key]
        if isinstance(value, dict):
            output.append(str(value.parent))
        output.append(str(key))
        output.append(str(value))
    assert output == expected_output

    expected_output = [
        str(sort_dictionary(data, reverse=True)),
        "bravo",
        str(sort_dictionary(data["bravo"], reverse=True)),
        "alfa",
        "alfa_value",
    ]
    json = JSON(data)
    json = json.sorted(reverse=True)
    assert_some_basic_truths(json)
    output = []
    for key in json:
        value = json[key]
        if isinstance(value, dict):
            output.append(str(value.parent))
        output.append(str(key))
        output.append(str(value))
    assert output == expected_output

    json = JSON()
    json["zulu"] = 123
    json["whiskey"] = {"victoria": "victoria_value"}
    assert json["whiskey"] == {"victoria": "victoria_value"}
    assert json["whiskey"].parent == json
    assert id(json["whiskey"].parent) == id(json)
