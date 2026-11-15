"""HTTP access for optional catalogue, survey and translation services."""
import os

import requests


def _check():
    if os.environ.get("ASTROWEB_OFFLINE") == "1":
        raise requests.ConnectionError("AstroWeb offline mode")


def get(*args, **kwargs):
    _check()
    return requests.get(*args, **kwargs)


def post(*args, **kwargs):
    _check()
    return requests.post(*args, **kwargs)
