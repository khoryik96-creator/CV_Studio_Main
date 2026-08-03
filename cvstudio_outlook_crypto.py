"""Outlook token-store cryptography (Phase 7B-6b).

Stateless AEAD helpers for the machine-bound Outlook token store extracted
from the legacy web shell. The stream cipher, record protect/unprotect and
Windows DPAPI transform are pure functions of their inputs; the install
identity material (machine hash + signing key) that binds the key to this
install is passed in by the caller rather than read from module globals, so
this module never imports ``app``.
"""

import base64
import json
import os
import hmac as _hmac
import hashlib as _hashlib


# Current on-disk record schema. The store also still accepts schema 1 records
# when unprotecting, for backward compatibility.
STORE_SCHEMA = 2


def store_key(schema, machine_hash, signing_key):
    """Derive the per-install symmetric key for the Outlook token store."""
    schema = int(schema or STORE_SCHEMA)
    material = (
        "CVStudio|OutlookTokenStore|v{}|".format(schema) + str(machine_hash or "")
    ).encode("utf-8")
    return _hmac.new(signing_key, material, _hashlib.sha256).digest()


def keystream(key, nonce, size):
    out = bytearray()
    counter = 0
    while len(out) < size:
        block = _hmac.new(key, nonce + counter.to_bytes(8, "big"), _hashlib.sha256).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:size])


def protect_record(record, machine_hash, signing_key, schema=None):
    schema = int(schema or STORE_SCHEMA)
    key = store_key(schema, machine_hash, signing_key)
    nonce = os.urandom(16)
    plain = json.dumps(record, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    stream = keystream(key, nonce, len(plain))
    cipher = bytes(a ^ b for a, b in zip(plain, stream))
    aad = ("CVStudio|OutlookTokenStore|v{}".format(schema)).encode("ascii")
    mac = _hmac.new(key, aad + nonce + cipher, _hashlib.sha256).hexdigest()
    return {
        "schema": schema,
        "nonce": base64.urlsafe_b64encode(nonce).decode("ascii"),
        "ciphertext": base64.urlsafe_b64encode(cipher).decode("ascii"),
        "mac": mac,
    }


def unprotect_record(payload, machine_hash, signing_key):
    if not isinstance(payload, dict):
        raise ValueError("Unsupported Outlook token store")
    schema = int(payload.get("schema") or 0)
    if schema not in (1, STORE_SCHEMA):
        raise ValueError("Unsupported Outlook token store")
    key = store_key(schema, machine_hash, signing_key)
    nonce = base64.urlsafe_b64decode(str(payload.get("nonce") or "").encode("ascii"))
    cipher = base64.urlsafe_b64decode(str(payload.get("ciphertext") or "").encode("ascii"))
    received = str(payload.get("mac") or "").lower()
    aad = ("CVStudio|OutlookTokenStore|v{}".format(schema)).encode("ascii")
    expected = _hmac.new(key, aad + nonce + cipher, _hashlib.sha256).hexdigest()
    if not received or not _hmac.compare_digest(received, expected):
        raise ValueError("Outlook token store integrity check failed")
    stream = keystream(key, nonce, len(cipher))
    plain = bytes(a ^ b for a, b in zip(cipher, stream))
    data = json.loads(plain.decode("utf-8"))
    return data if isinstance(data, dict) else {}


def dpapi_transform(data, protect=True):
    if os.name != "nt":
        raise RuntimeError("Windows DPAPI is unavailable")
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

    raw = bytes(data or b"")
    buffer = ctypes.create_string_buffer(raw, max(1, len(raw)))
    in_blob = DATA_BLOB(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    out_blob = DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    flags = 0x1  # CRYPTPROTECT_UI_FORBIDDEN
    if protect:
        ok = crypt32.CryptProtectData(ctypes.byref(in_blob), "CV Studio Outlook", None, None, None, flags, ctypes.byref(out_blob))
    else:
        ok = crypt32.CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, flags, ctypes.byref(out_blob))
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        if out_blob.pbData:
            kernel32.LocalFree(out_blob.pbData)
