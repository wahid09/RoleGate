"""A tiny software authenticator (ES256, "none" attestation) for tests."""

import hashlib
import json
import os
import struct

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from webauthn.helpers import bytes_to_base64url


class SoftAuthenticator:
    def __init__(self, rp_id="localhost", origin="http://localhost"):
        self.rp_id = rp_id
        self.origin = origin
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = os.urandom(32)
        self.sign_count = 0

    def _client_data(self, type_, challenge_b64, origin=None):
        return json.dumps(
            {"type": type_, "challenge": challenge_b64, "origin": origin or self.origin, "crossOrigin": False}
        ).encode()

    def _cose_key(self):
        nums = self.key.public_key().public_numbers()
        return cbor2.dumps({1: 2, 3: -7, -1: 1, -2: nums.x.to_bytes(32, "big"), -3: nums.y.to_bytes(32, "big")})

    def create(self, options: dict, origin=None) -> dict:
        rp_hash = hashlib.sha256(self.rp_id.encode()).digest()
        flags = 0x01 | 0x04 | 0x40  # user present, user verified, attested credential data
        auth_data = (
            rp_hash + bytes([flags]) + struct.pack(">I", self.sign_count)
            + bytes(16) + struct.pack(">H", len(self.credential_id)) + self.credential_id + self._cose_key()
        )
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        cid = bytes_to_base64url(self.credential_id)
        return {
            "id": cid,
            "rawId": cid,
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(self._client_data("webauthn.create", options["challenge"], origin)),
                "attestationObject": bytes_to_base64url(attestation),
                "transports": ["internal"],
            },
            "clientExtensionResults": {},
        }

    def get(self, options: dict, origin=None, bump=True) -> dict:
        if bump:
            self.sign_count += 1
        rp_hash = hashlib.sha256(self.rp_id.encode()).digest()
        auth_data = rp_hash + bytes([0x01 | 0x04]) + struct.pack(">I", self.sign_count)
        client_data = self._client_data("webauthn.get", options["challenge"], origin)
        signature = self.key.sign(auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))
        cid = bytes_to_base64url(self.credential_id)
        return {
            "id": cid,
            "rawId": cid,
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "authenticatorData": bytes_to_base64url(auth_data),
                "signature": bytes_to_base64url(signature),
                "userHandle": options.get("user_handle") or None,
            },
            "clientExtensionResults": {},
        }


