"""Thin wrappers around py-webauthn so the router stays readable and testable."""

import hashlib
import hmac

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.exceptions import (
    InvalidAuthenticationResponse,
    InvalidJSONStructure,
    InvalidRegistrationResponse,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from .config import settings

__all__ = [
    "VERIFY_ERRORS",
    "InvalidAuthenticationResponse",
    "InvalidRegistrationResponse",
    "authentication_options",
    "registration_options",
    "user_handle",
    "verify_authentication",
    "verify_registration",
]

# what a bad or malformed browser payload can raise from py-webauthn
VERIFY_ERRORS = (InvalidAuthenticationResponse, InvalidJSONStructure, ValueError, KeyError, TypeError)
def user_handle(user_id: int) -> bytes:
    """Stable, opaque per-user id. Never the email, never the raw database id."""
    return hmac.new(settings.SECRET_KEY.encode(), f"webauthn:{user_id}".encode(), hashlib.sha256).digest()


def _descriptors(credential_ids: list[str]) -> list[PublicKeyCredentialDescriptor]:
    return [PublicKeyCredentialDescriptor(id=base64url_to_bytes(c)) for c in credential_ids]


def registration_options(user_id: int, email: str, existing_ids: list[str]) -> tuple[str, bytes]:
    """Return (options as JSON text, challenge bytes)."""
    options = generate_registration_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        rp_name=settings.WEBAUTHN_RP_NAME,
        user_id=user_handle(user_id),
        user_name=email,
        exclude_credentials=_descriptors(existing_ids),
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )
    return options_to_json(options), options.challenge


def authentication_options(credential_ids: list[str]) -> tuple[str, bytes]:
    options = generate_authentication_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        allow_credentials=_descriptors(credential_ids),
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    return options_to_json(options), options.challenge


def verify_registration(credential: dict, challenge: bytes):
    return verify_registration_response(
        credential=credential,
        expected_challenge=challenge,
        expected_rp_id=settings.WEBAUTHN_RP_ID,
        expected_origin=settings.webauthn_origins,
    )


def verify_authentication(credential: dict, challenge: bytes, public_key: bytes, sign_count: int):
    return verify_authentication_response(
        credential=credential,
        expected_challenge=challenge,
        expected_rp_id=settings.WEBAUTHN_RP_ID,
        expected_origin=settings.webauthn_origins,
        credential_public_key=public_key,
        credential_current_sign_count=sign_count,
    )


def b64(data: bytes) -> str:
    return bytes_to_base64url(data)
