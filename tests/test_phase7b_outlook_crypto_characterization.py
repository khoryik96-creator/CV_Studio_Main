"""Characterization tests for the Outlook token-store cryptography helpers.

Locks the behaviour of the stateless AEAD helpers extracted into
``cvstudio_outlook_crypto`` (Phase 7B-6b): deterministic key derivation,
keystream, authenticated protect/unprotect round-trips, tamper detection, and
schema handling. Install identity material is supplied explicitly, so these
run without Flask, files, or platform secret stores.
"""

import unittest

import cvstudio_outlook_crypto as oc


MACHINE = "machine-hash-abc123"
SIGNING = b"signing-key-bytes-0123456789abcdef"


class KeyAndStreamTests(unittest.TestCase):
    def test_store_key_is_deterministic_and_binds_identity(self):
        k1 = oc.store_key(oc.STORE_SCHEMA, MACHINE, SIGNING)
        k2 = oc.store_key(oc.STORE_SCHEMA, MACHINE, SIGNING)
        self.assertEqual(k1, k2)
        self.assertEqual(len(k1), 32)
        # Different machine hash or signing key => different key.
        self.assertNotEqual(k1, oc.store_key(oc.STORE_SCHEMA, "other-machine", SIGNING))
        self.assertNotEqual(k1, oc.store_key(oc.STORE_SCHEMA, MACHINE, b"other-signing-key"))

    def test_store_key_schema_default(self):
        self.assertEqual(
            oc.store_key(None, MACHINE, SIGNING),
            oc.store_key(oc.STORE_SCHEMA, MACHINE, SIGNING),
        )

    def test_keystream_length_and_determinism(self):
        key = oc.store_key(oc.STORE_SCHEMA, MACHINE, SIGNING)
        s1 = oc.keystream(key, b"nonce-16-bytes!!", 40)
        s2 = oc.keystream(key, b"nonce-16-bytes!!", 40)
        self.assertEqual(len(s1), 40)
        self.assertEqual(s1, s2)
        self.assertNotEqual(s1, oc.keystream(key, b"different-nonce!", 40))


class ProtectRoundTripTests(unittest.TestCase):
    def test_protect_unprotect_round_trip(self):
        record = {"access_token": "AAA", "refresh_token": "BBB", "expires_at": 123, "nested": {"x": 1}}
        blob = oc.protect_record(record, MACHINE, SIGNING)
        self.assertEqual(blob["schema"], oc.STORE_SCHEMA)
        self.assertIn("nonce", blob)
        self.assertIn("ciphertext", blob)
        self.assertIn("mac", blob)
        # Ciphertext must not leak the plaintext token.
        self.assertNotIn("AAA", blob["ciphertext"])
        restored = oc.unprotect_record(blob, MACHINE, SIGNING)
        self.assertEqual(restored, record)

    def test_nonce_is_randomised_per_call(self):
        record = {"a": 1}
        b1 = oc.protect_record(record, MACHINE, SIGNING)
        b2 = oc.protect_record(record, MACHINE, SIGNING)
        self.assertNotEqual(b1["nonce"], b2["nonce"])
        self.assertNotEqual(b1["ciphertext"], b2["ciphertext"])
        self.assertEqual(oc.unprotect_record(b1, MACHINE, SIGNING), record)
        self.assertEqual(oc.unprotect_record(b2, MACHINE, SIGNING), record)

    def test_wrong_identity_fails_integrity(self):
        blob = oc.protect_record({"t": "x"}, MACHINE, SIGNING)
        with self.assertRaises(ValueError):
            oc.unprotect_record(blob, "wrong-machine", SIGNING)
        with self.assertRaises(ValueError):
            oc.unprotect_record(blob, MACHINE, b"wrong-signing-key")

    def test_tampered_ciphertext_is_rejected(self):
        blob = oc.protect_record({"t": "x"}, MACHINE, SIGNING)
        tampered = dict(blob)
        # Flip the mac -> integrity check must fail.
        tampered["mac"] = ("0" * len(blob["mac"]))
        with self.assertRaises(ValueError):
            oc.unprotect_record(tampered, MACHINE, SIGNING)

    def test_unsupported_schema_rejected(self):
        with self.assertRaises(ValueError):
            oc.unprotect_record({"schema": 99, "nonce": "", "ciphertext": "", "mac": ""}, MACHINE, SIGNING)
        with self.assertRaises(ValueError):
            oc.unprotect_record("not-a-dict", MACHINE, SIGNING)


class DpapiTests(unittest.TestCase):
    def test_dpapi_transform_requires_windows(self):
        import os
        if os.name != "nt":
            with self.assertRaises(RuntimeError):
                oc.dpapi_transform(b"data", protect=True)


if __name__ == "__main__":
    unittest.main()
