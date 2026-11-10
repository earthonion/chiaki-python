#!/usr/bin/env python3
"""Register a PS5 for local Remote Play and save the resulting profile as JSON."""

import argparse
import ctypes
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chiaki_python import _chiaki


class RegistInfo(ctypes.Structure):
    _fields_ = [
        ("target", ctypes.c_int),
        ("host", ctypes.c_char_p),
        ("broadcast", ctypes.c_bool),
        ("psn_online_id", ctypes.c_char_p),
        ("psn_account_id", ctypes.c_uint8 * 8),
        ("pin", ctypes.c_uint32),
        ("console_pin", ctypes.c_uint32),
        ("holepunch_info", ctypes.c_void_p),
        ("rudp", ctypes.c_byte * 512),
    ]


class RegisteredHost(ctypes.Structure):
    _fields_ = [
        ("target", ctypes.c_int),
        ("ap_ssid", ctypes.c_char * 0x30),
        ("ap_bssid", ctypes.c_char * 0x20),
        ("ap_key", ctypes.c_char * 0x50),
        ("ap_name", ctypes.c_char * 0x20),
        ("server_mac", ctypes.c_uint8 * 6),
        ("server_nickname", ctypes.c_char * 0x20),
        ("rp_regist_key", ctypes.c_uint8 * 0x10),
        ("rp_key_type", ctypes.c_uint32),
        ("rp_key", ctypes.c_uint8 * 0x10),
        ("console_pin", ctypes.c_uint32),
    ]


class RegistEvent(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int), ("registered_host", ctypes.POINTER(RegisteredHost))]


CALLBACK = ctypes.CFUNCTYPE(None, ctypes.POINTER(RegistEvent), ctypes.c_void_p)


def register(host, pin, account_id_hex, output, target):
    result = {}

    def finished(event, _user):
        kind = event.contents.type
        result["status"] = kind
        if kind != 2:
            return
        h = event.contents.registered_host.contents
        result["profile"] = {
            "name": bytes(h.server_nickname).split(b"\0", 1)[0].decode("ascii", "replace"),
            "host": host,
            "target": h.target,
            "is_ps5": True,
            "mac": ":".join(f"{value:02X}" for value in h.server_mac),
            "regist_key": bytes(h.rp_regist_key).rstrip(b"\0").decode("ascii"),
            "rp_key": bytes(h.rp_key).hex(),
        }

    callback = CALLBACK(finished)
    log_callback = _chiaki.ChiakiLogCb(lambda *_args: None)
    log = _chiaki.ChiakiLog(0, log_callback, None)
    lib = _chiaki._lib
    lib.chiaki_lib_init()
    lib.chiaki_regist_start.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(RegistInfo), CALLBACK, ctypes.c_void_p,
    ]
    lib.chiaki_regist_start.restype = ctypes.c_uint32
    lib.chiaki_regist_fini.argtypes = [ctypes.c_void_p]
    lib.chiaki_regist_stop.argtypes = [ctypes.c_void_p]

    info = RegistInfo()
    info.target = target
    info.host = host.encode()
    info.broadcast = False
    info.psn_online_id = None
    info.psn_account_id = (ctypes.c_uint8 * 8)(*bytes.fromhex(account_id_hex))
    info.pin = pin
    info.console_pin = 0
    info.holepunch_info = None
    regist = ctypes.create_string_buffer(4096)
    error = lib.chiaki_regist_start(regist, ctypes.byref(log), ctypes.byref(info), callback, None)
    if error:
        raise RuntimeError(f"registration start failed: {error}")

    deadline = time.time() + 20
    while "status" not in result and time.time() < deadline:
        time.sleep(0.1)
    if "status" not in result:
        lib.chiaki_regist_stop(regist)
    lib.chiaki_regist_fini(regist)

    if result.get("status") != 2:
        return False
    with open(output, "w") as stream:
        json.dump(result["profile"], stream)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("host")
    parser.add_argument("pin", type=lambda value: int(value, 10))
    parser.add_argument("output")
    parser.add_argument("--account-id-hex", required=True)
    parser.add_argument("--target", type=int, default=1000100)
    args = parser.parse_args()
    if len(bytes.fromhex(args.account_id_hex)) != 8:
        parser.error("account ID must contain exactly 8 bytes of hex")
    success = register(args.host, args.pin, args.account_id_hex, args.output, args.target)
    print("registration succeeded" if success else "registration failed")
    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    main()
