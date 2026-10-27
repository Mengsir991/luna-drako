#!/usr/bin/env python3
"""Download the official stock firmware for the Lunafury TYPE33 EVO.

The ".xvi" file is a plain, unencrypted Intel HEX image. Vendor URL taken from
the official web driver (mouse.lunafury.games, model TYPE33_54H).
"""
import hashlib
import sys
import urllib.request

URL = ("https://mouse.lunafury.games/fwfiles/TYPE33/"
       "TYPE33_Mouse_54H20_App_v0.0.1.48_20261013.xvi")
OUT = "TYPE33_Mouse_54H20_App_v0.0.1.48_20261013.xvi"

print(f"downloading {URL}")
urllib.request.urlretrieve(URL, OUT)
data = open(OUT, "rb").read()
print(f"saved {OUT}  ({len(data)} bytes)")
print(f"sha256 {hashlib.sha256(data).hexdigest()}")
assert data[:1] == b":" and data.splitlines()[0].decode().startswith(":02000004"), \
    "not an Intel HEX file - vendor may have changed the format"
print("looks like a valid Intel HEX image")
