"""
Copyright 2022 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.

OAuth2 client configuration for `OAAClient`.

Configuration classes only describe *how* to request an access token. The `OAAClient` owns the HTTP
call, token storage and refresh.

Example:
    ```python
    from oaaclient.auth import ClientCredentialsConfig
    from oaaclient.client import OAAClient

    config = ClientCredentialsConfig(client_id="my-client", client_secret="...")
    veza_con = OAAClient("tenant.vezacloud.com", oauth_config=config)
    ```

JWT bearer signing requires the `cryptography` package (`pip install oaaclient[jwt]`).
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import time
import urllib.parse
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar

# path appended to the Veza URL when the config does not provide an explicit token_url
DEFAULT_TOKEN_PATH = "/oauth/token"

JWT_BEARER_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:jwt-bearer"
CLIENT_CREDENTIALS_GRANT_TYPE = "client_credentials"

SUPPORTED_JWT_ALGORITHMS = ("RS256", "ES256")

ENV_CLIENT_ID = "VEZA_OAUTH_CLIENT_ID"
ENV_CLIENT_SECRET = "VEZA_OAUTH_CLIENT_SECRET"
ENV_PRIVATE_KEY_PATH = "VEZA_OAUTH_PRIVATE_KEY_PATH"
ENV_PRIVATE_KEY_BASE64 = "VEZA_OAUTH_PRIVATE_KEY_BASE64"
ENV_PRIVATE_KEY_PASSWORD = "VEZA_OAUTH_PRIVATE_KEY_PASSWORD"
ENV_KEY_ID = "VEZA_OAUTH_KEY_ID"
ENV_SCOPE = "VEZA_OAUTH_SCOPE"
ENV_TOKEN_URL = "VEZA_OAUTH_TOKEN_URL"


@dataclass
class OAuthConfig(ABC):
    """Base class for OAuth2 client configuration

    Use one of the concrete classes, `ClientCredentialsConfig` or `JWTBearerConfig`.

    Args:
        client_id (str): OAuth client ID
        scope (str, optional): Scope to request. Omitted from the request when not set.
        token_url (str, optional): Override for the token endpoint. Defaults to `<veza url>/oauth/token`
    """
    client_id: str = ""
    scope: str | None = None
    token_url: str | None = None

    def __post_init__(self) -> None:
        if not self.client_id:
            raise ValueError("OAuth client_id is required")
        # the client secret or signed assertion is sent to this URL, never allow clear text
        if self.token_url and urllib.parse.urlsplit(self.token_url).scheme.lower() != "https":
            raise ValueError("OAuth token_url must use https")

    def resolve_token_url(self, veza_url: str) -> str:
        """Return the token endpoint to use for the given Veza URL"""
        return self.token_url or f"{veza_url.rstrip('/')}{DEFAULT_TOKEN_PATH}"

    @abstractmethod
    def build_token_request(self, token_url: str) -> dict:
        """Build the form body for the token request

        Called for every token request, so time sensitive values (e.g. JWT assertions) are always fresh.

        Args:
            token_url (str): Resolved token endpoint URL

        Returns:
            dict: Form fields to POST to the token endpoint
        """

    @classmethod
    def from_env(cls) -> OAuthConfig | None:
        """Build a configuration from `VEZA_OAUTH_*` environment variables

        - `VEZA_OAUTH_CLIENT_ID` (required to enable OAuth)
        - `VEZA_OAUTH_CLIENT_SECRET` selects the client credentials flow
        - `VEZA_OAUTH_PRIVATE_KEY_PATH` or `VEZA_OAUTH_PRIVATE_KEY_BASE64` selects the JWT bearer flow (optional `VEZA_OAUTH_KEY_ID`)
        - `VEZA_OAUTH_PRIVATE_KEY_PASSWORD` is optional, for an encrypted private key
        - `VEZA_OAUTH_SCOPE` and `VEZA_OAUTH_TOKEN_URL` are optional

        Returns:
            OAuthConfig | None: Configuration, or None when `VEZA_OAUTH_CLIENT_ID` is not set

        Raises:
            ValueError: When the client ID is set but the secret/key settings are missing or conflicting
        """
        client_id = os.getenv(ENV_CLIENT_ID)
        if not client_id:
            return None

        secret = os.getenv(ENV_CLIENT_SECRET)
        key_path = os.getenv(ENV_PRIVATE_KEY_PATH)
        key_base64 = os.getenv(ENV_PRIVATE_KEY_BASE64)
        common = {
            "client_id": client_id,
            "scope": os.getenv(ENV_SCOPE) or None,
            "token_url": os.getenv(ENV_TOKEN_URL) or None,
        }

        if sum(bool(v) for v in (secret, key_path, key_base64)) > 1:
            raise ValueError(f"Set only one of {ENV_CLIENT_SECRET}, {ENV_PRIVATE_KEY_PATH} and {ENV_PRIVATE_KEY_BASE64}")
        if secret:
            return ClientCredentialsConfig(client_secret=secret, **common)
        if key_path or key_base64:
            return JWTBearerConfig(private_key_path=key_path or None, private_key_base64=key_base64 or None,
                                   key_id=os.getenv(ENV_KEY_ID) or None,
                                   private_key_password=os.getenv(ENV_PRIVATE_KEY_PASSWORD) or None, **common)
        raise ValueError(f"{ENV_CLIENT_ID} is set, but none of {ENV_CLIENT_SECRET}, {ENV_PRIVATE_KEY_PATH} or {ENV_PRIVATE_KEY_BASE64} is set")

    @classmethod
    def from_dict(cls, config: dict) -> OAuthConfig:
        """Build a configuration from a dictionary, e.g. loaded from an auth JSON file

        The `type` key selects the flow: `client_credentials` (default when `client_secret` is present)
        or `jwt_bearer` (default when a private key setting is present). Remaining keys are passed to the
        matching class.

        Raises:
            ValueError: For unknown type or invalid settings
        """
        config = dict(config)
        flow = config.pop("type", None)
        if flow is None:
            if "client_secret" in config:
                flow = "client_credentials"
            elif any(k in config for k in ("private_key_path", "private_key", "private_key_base64")):
                flow = "jwt_bearer"
        try:
            if flow == "client_credentials":
                return ClientCredentialsConfig(**config)
            if flow == "jwt_bearer":
                return JWTBearerConfig(**config)
        except TypeError as e:
            raise ValueError(f"Invalid OAuth configuration: {e}") from e
        raise ValueError(f"Unknown or missing OAuth type {flow!r}, expected 'client_credentials' or 'jwt_bearer'")


@dataclass
class ClientCredentialsConfig(OAuthConfig):
    """OAuth2 client credentials flow (client ID and secret)

    Args:
        client_id (str): OAuth client ID
        client_secret (str): OAuth client secret
        scope (str, optional): Scope to request
        token_url (str, optional): Override for the token endpoint
    """
    client_secret: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.client_secret:
            raise ValueError("OAuth client_secret is required for client credentials flow")

    def build_token_request(self, token_url: str) -> dict:
        body = {
            "grant_type": CLIENT_CREDENTIALS_GRANT_TYPE,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        if self.scope:
            body["scope"] = self.scope
        return body


@dataclass
class JWTBearerConfig(OAuthConfig):
    """OAuth2 JWT bearer flow

    The client signs an assertion with a private key matching the public key uploaded to the OAuth client in Veza.
    Provide the key in exactly one form: PEM content (`private_key`), a file path (`private_key_path`), or the
    PEM file content base64 encoded (`private_key_base64`), which is convenient for environment variables and
    secret stores since it contains no newlines.

    The key is loaded and validated when the config is created, so a missing file, an encrypted key without
    `private_key_password`, or a key that does not match `algorithm` raises `ValueError` immediately. The key
    is read once, a rotated key file requires creating a new config.

    Args:
        client_id (str): OAuth client ID
        private_key (str | bytes, optional): PEM encoded private key
        private_key_path (str, optional): Path to a PEM encoded private key file
        private_key_base64 (str, optional): Base64 encoding of the PEM private key content
        private_key_password (str | bytes, optional): Passphrase for an encrypted private key
        key_id (str, optional): Value for the `kid` JWT header
        algorithm (str, optional): `RS256` (RSA, default) or `ES256` (ECDSA P-256)
        assertion_lifetime (int, optional): Lifetime of the signed assertion in seconds. Defaults to 300.
        scope (str, optional): Scope to request
        token_url (str, optional): Override for the token endpoint
    """
    private_key: str | bytes | None = field(default=None, repr=False)
    private_key_path: str | None = None
    private_key_base64: str | None = field(default=None, repr=False)
    key_id: str | None = None
    algorithm: str = "RS256"
    assertion_lifetime: int = 300
    # backdate `iat` to tolerate the local clock running ahead of Veza
    IAT_BACKDATE_SECONDS: ClassVar[int] = 30
    private_key_password: str | bytes | None = field(default=None, repr=False)
    # loaded key object, set by __post_init__
    _key: object = field(init=False, default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        if sum(bool(v) for v in (self.private_key, self.private_key_path, self.private_key_base64)) != 1:
            raise ValueError("Provide exactly one of private_key, private_key_path and private_key_base64")
        if self.private_key_base64:
            # validate early so a bad value fails at configuration time
            self._decode_base64_key()
        if self.algorithm not in SUPPORTED_JWT_ALGORITHMS:
            raise ValueError(f"Unsupported JWT algorithm {self.algorithm!r}, must be one of {SUPPORTED_JWT_ALGORITHMS}")
        if self.assertion_lifetime <= 0:
            raise ValueError("assertion_lifetime must be positive")
        self._key = self._load_private_key()

    def _decode_base64_key(self) -> bytes:
        try:
            # strip all whitespace, secret stores and mounted files often add trailing newlines or wrapped lines
            return base64.b64decode("".join(self.private_key_base64.split()), validate=True)
        except (binascii.Error, ValueError) as e:
            raise ValueError("private_key_base64 is not valid base64") from e

    def _load_private_key(self):
        try:
            from cryptography.hazmat.primitives import serialization
        except ImportError as e:
            raise ImportError("JWT bearer authentication requires the 'cryptography' package, install with `pip install oaaclient[jwt]`") from e

        from cryptography.hazmat.primitives.asymmetric import ec, rsa

        key_data = self.private_key
        if self.private_key_path:
            try:
                with open(self.private_key_path, "rb") as f:
                    key_data = f.read()
            except OSError as e:
                raise ValueError(f"Unable to read private key file {self.private_key_path}: {e.strerror or e}") from e
        elif self.private_key_base64:
            key_data = self._decode_base64_key()
        if isinstance(key_data, str):
            key_data = key_data.encode()

        password = self.private_key_password
        if isinstance(password, str):
            password = password.encode()

        try:
            key = serialization.load_pem_private_key(key_data, password=password)
        except TypeError as e:
            if password is None:
                raise ValueError("Private key is encrypted, provide private_key_password") from e
            raise ValueError("private_key_password was provided but the private key is not encrypted") from e
        except Exception as e:
            # ValueError for malformed or wrong password, UnsupportedAlgorithm for unsupported key types
            raise ValueError(f"Unable to load private key, expected an unencrypted or correctly password protected PEM key: {e}") from e

        if self.algorithm == "RS256":
            if not isinstance(key, rsa.RSAPrivateKey):
                raise ValueError(f"RS256 requires an RSA private key, got {type(key).__name__}")
        else:
            if not isinstance(key, ec.EllipticCurvePrivateKey):
                raise ValueError(f"ES256 requires an EC private key, got {type(key).__name__}")
            if key.curve.name != "secp256r1":
                raise ValueError(f"ES256 requires a P-256 (secp256r1) key, got {key.curve.name}")
        return key

    @staticmethod
    def _b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    def _sign(self, signing_input: bytes) -> bytes:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec, padding
        from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

        key = self._key
        if self.algorithm == "RS256":
            return key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())

        # ES256: convert DER signature to the fixed width r||s form required by JWS
        der = key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(der)
        return r.to_bytes(32, "big") + s.to_bytes(32, "big")

    def build_assertion(self, token_url: str) -> str:
        """Create a freshly signed JWT assertion

        Claims: `iss` and `sub` are the client ID, `aud` is the token URL, plus `iat`, `exp` and `jti`.
        """
        now = int(time.time())
        header = {"alg": self.algorithm, "typ": "JWT"}
        if self.key_id:
            header["kid"] = self.key_id
        claims = {
            "iss": self.client_id,
            "sub": self.client_id,
            "aud": token_url,
            "iat": now - self.IAT_BACKDATE_SECONDS,
            "exp": now + self.assertion_lifetime - self.IAT_BACKDATE_SECONDS,
            "jti": str(uuid.uuid4()),
        }
        signing_input = ".".join(
            self._b64(json.dumps(part, separators=(",", ":")).encode()) for part in (header, claims)
        )
        signature = self._sign(signing_input.encode())
        return f"{signing_input}.{self._b64(signature)}"

    def build_token_request(self, token_url: str) -> dict:
        body = {
            "grant_type": JWT_BEARER_GRANT_TYPE,
            "assertion": self.build_assertion(token_url),
        }
        if self.scope:
            body["scope"] = self.scope
        return body
