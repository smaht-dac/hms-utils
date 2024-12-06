import json
from typing import Union


def dj(data: Union[dict, list]) -> None:
    print(json.dumps(data, indent=4))
