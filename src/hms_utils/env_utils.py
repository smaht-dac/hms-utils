import os
from contextlib import contextmanager


@contextmanager
def os_environ(key: str, value: str):
    saved_value = os.environ.get(key)
    try:
        os.environ[key] = value
        yield
    finally:
        if saved_value is not None:
            os.environ[key] = saved_value
        else:
            del os.environ[key]
