"""
Copyright 2022 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

import base64
import json
import inspect
import logging
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import MagicMock, patch

import pytest
import requests

from generate_app import generate_app

from oaaclient import auth
from oaaclient.auth import ClientCredentialsConfig, JWTBearerConfig, OAuthConfig
from oaaclient.client import OAAClient, OAAClientError, OAAConnectionError, OAAResponseError

log = logging.getLogger(__name__)

# timeout for the push test if the datasource does not parse
TEST_TIMEOUT = int(os.getenv("OAA_PUSH_TIMEOUT", 300))

# matches datasource status values that indicate a parsing failure
FAILURE_REGEX = re.compile(r"fail|error", re.IGNORECASE)

# placeholder for mocked tests only, .invalid is a reserved TLD (RFC 2606) that never resolves.
# Live tests must take the host from PYTEST_VEZA_HOST.
URL = "https://veza.invalid"
TOKEN_URL = f"{URL}/oauth/token"

OAUTH_ENV = [auth.ENV_PRIVATE_KEY_PASSWORD, auth.ENV_CLIENT_ID, auth.ENV_CLIENT_SECRET, auth.ENV_PRIVATE_KEY_PATH, auth.ENV_PRIVATE_KEY_BASE64, auth.ENV_KEY_ID, auth.ENV_SCOPE, auth.ENV_TOKEN_URL, "VEZA_API_KEY"]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in OAUTH_ENV:
        monkeypatch.delenv(name, raising=False)


def token_response(token="tok-1", expires_in=43200, status=200, body=None):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status
    resp.ok = status < 400
    resp.reason = "reason"
    resp.json.return_value = body if body is not None else {"access_token": token, "token_type": "Bearer", "expires_in": expires_in}
    return resp


def make_client(config=None, post=None, **kwargs):
    """Create a client with network calls mocked out"""
    with patch.object(OAAClient, "_test_connection"), patch("requests.Session.post", return_value=post or token_response()):
        return OAAClient(URL, oauth_config=config, **kwargs)


def b64decode(part):
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


# ---- config classes ----

def test_client_credentials_request():
    config = ClientCredentialsConfig(client_id="id", client_secret="secret")
    assert config.build_token_request(TOKEN_URL) == {"grant_type": "client_credentials", "client_id": "id", "client_secret": "secret"}
    config.scope = "read"
    assert config.build_token_request(TOKEN_URL)["scope"] == "read"


def test_secret_not_in_repr():
    config = ClientCredentialsConfig(client_id="id", client_secret="supersecret")
    assert "supersecret" not in repr(config)


def test_config_validation():
    with pytest.raises(ValueError):
        ClientCredentialsConfig(client_id="", client_secret="s")
    with pytest.raises(ValueError):
        ClientCredentialsConfig(client_id="id")
    with pytest.raises(ValueError):
        JWTBearerConfig(client_id="id")
    with pytest.raises(ValueError):
        JWTBearerConfig(client_id="id", private_key="a", private_key_path="b")
    with pytest.raises(ValueError):
        JWTBearerConfig(client_id="id", private_key="a", private_key_base64="YQ==")
    with pytest.raises(ValueError, match="base64"):
        JWTBearerConfig(client_id="id", private_key_base64="not base64!!")
    with pytest.raises(ValueError):
        JWTBearerConfig(client_id="id", private_key="a", algorithm="HS256")
    with pytest.raises(ValueError):
        JWTBearerConfig(client_id="id", private_key="a", assertion_lifetime=0)


def test_resolve_token_url():
    config = ClientCredentialsConfig(client_id="id", client_secret="s")
    assert config.resolve_token_url(f"{URL}/") == TOKEN_URL
    config.token_url = "https://other.invalid/token"
    assert config.resolve_token_url(URL) == "https://other.invalid/token"


def test_from_env_none():
    assert OAuthConfig.from_env() is None


def test_from_env_client_credentials(monkeypatch):
    monkeypatch.setenv(auth.ENV_CLIENT_ID, "id")
    monkeypatch.setenv(auth.ENV_CLIENT_SECRET, "secret")
    monkeypatch.setenv(auth.ENV_SCOPE, "s1")
    config = OAuthConfig.from_env()
    assert isinstance(config, ClientCredentialsConfig)
    assert (config.client_id, config.client_secret, config.scope) == ("id", "secret", "s1")


def test_from_env_jwt(monkeypatch, rsa_key, tmp_path):
    key_file = tmp_path / "key.pem"
    key_file.write_bytes(rsa_key[1])
    monkeypatch.setenv(auth.ENV_CLIENT_ID, "id")
    monkeypatch.setenv(auth.ENV_PRIVATE_KEY_PATH, str(key_file))
    monkeypatch.setenv(auth.ENV_KEY_ID, "kid1")
    config = OAuthConfig.from_env()
    assert isinstance(config, JWTBearerConfig)
    assert (config.private_key_path, config.key_id) == (str(key_file), "kid1")


def test_from_env_jwt_base64(monkeypatch, rsa_key):
    encoded = base64.b64encode(rsa_key[1]).decode()
    monkeypatch.setenv(auth.ENV_CLIENT_ID, "id")
    monkeypatch.setenv(auth.ENV_PRIVATE_KEY_BASE64, encoded)
    config = OAuthConfig.from_env()
    assert isinstance(config, JWTBearerConfig)
    assert config.private_key_base64 == encoded and config.private_key_path is None
    monkeypatch.setenv(auth.ENV_PRIVATE_KEY_PATH, "/tmp/key.pem")
    with pytest.raises(ValueError):
        OAuthConfig.from_env()


def test_from_env_errors(monkeypatch):
    monkeypatch.setenv(auth.ENV_CLIENT_ID, "id")
    with pytest.raises(ValueError):
        OAuthConfig.from_env()
    monkeypatch.setenv(auth.ENV_CLIENT_SECRET, "s")
    monkeypatch.setenv(auth.ENV_PRIVATE_KEY_PATH, "/tmp/key.pem")
    with pytest.raises(ValueError):
        OAuthConfig.from_env()


def test_from_dict(rsa_key):
    pem = rsa_key[1].decode()
    assert isinstance(OAuthConfig.from_dict({"client_id": "id", "client_secret": "s"}), ClientCredentialsConfig)
    assert isinstance(OAuthConfig.from_dict({"type": "jwt_bearer", "client_id": "id", "private_key": pem}), JWTBearerConfig)
    assert isinstance(OAuthConfig.from_dict({"client_id": "id", "private_key_base64": base64.b64encode(pem.encode()).decode()}), JWTBearerConfig)
    with pytest.raises(ValueError):
        OAuthConfig.from_dict({"client_id": "id"})
    with pytest.raises(ValueError):
        OAuthConfig.from_dict({"type": "client_credentials", "client_id": "id", "client_secret": "s", "bogus": 1})


# ---- JWT signing ----

@pytest.fixture
def rsa_key():
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    return key, pem


@pytest.fixture
def ec_key():
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    return key, pem


def test_jwt_rs256_assertion(rsa_key):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    key, pem = rsa_key
    config = JWTBearerConfig(client_id="id", private_key=pem, key_id="kid1", scope="s")
    body = config.build_token_request(TOKEN_URL)
    assert body["grant_type"] == auth.JWT_BEARER_GRANT_TYPE
    assert body["scope"] == "s"

    header_b64, claims_b64, sig_b64 = body["assertion"].split(".")
    header = json.loads(b64decode(header_b64))
    claims = json.loads(b64decode(claims_b64))
    assert header == {"alg": "RS256", "typ": "JWT", "kid": "kid1"}
    assert claims["iss"] == claims["sub"] == "id"
    assert claims["aud"] == TOKEN_URL
    # iat is backdated to tolerate clock skew, exp is relative to the current time
    assert claims["exp"] - claims["iat"] == 300
    assert claims["iat"] < time.time()
    # signature verifies (raises on failure)
    key.public_key().verify(b64decode(sig_b64), f"{header_b64}.{claims_b64}".encode(), padding.PKCS1v15(), hashes.SHA256())


def test_jwt_base64_key(rsa_key):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    key, pem = rsa_key
    encoded = base64.b64encode(pem).decode()
    assert encoded not in repr(JWTBearerConfig(client_id="id", private_key_base64=encoded))
    config = JWTBearerConfig(client_id="id", private_key_base64=encoded)
    header_b64, claims_b64, sig_b64 = config.build_assertion(TOKEN_URL).split(".")
    key.public_key().verify(b64decode(sig_b64), f"{header_b64}.{claims_b64}".encode(), padding.PKCS1v15(), hashes.SHA256())


@pytest.mark.parametrize("wrap", [lambda e: e + "\n", lambda e: "\n".join(e[i:i + 64] for i in range(0, len(e), 64)) + "\n"], ids=["trailing-newline", "wrapped"])
def test_jwt_base64_key_ignores_whitespace(rsa_key, wrap):
    _, pem = rsa_key
    encoded = wrap(base64.b64encode(pem).decode())
    config = JWTBearerConfig(client_id="id", private_key_base64=encoded)
    assert config.build_assertion(TOKEN_URL).count(".") == 2


def test_jwt_unique_assertions(rsa_key):
    _, pem = rsa_key
    config = JWTBearerConfig(client_id="id", private_key=pem.decode())
    a = config.build_token_request(TOKEN_URL)["assertion"]
    b = config.build_token_request(TOKEN_URL)["assertion"]
    assert a != b


def test_jwt_es256_assertion_from_file(ec_key, tmp_path):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
    key, pem = ec_key
    key_file = tmp_path / "key.pem"
    key_file.write_bytes(pem)
    config = JWTBearerConfig(client_id="id", private_key_path=str(key_file), algorithm="ES256")
    header_b64, claims_b64, sig_b64 = config.build_assertion(TOKEN_URL).split(".")
    assert "kid" not in json.loads(b64decode(header_b64))
    raw = b64decode(sig_b64)
    assert len(raw) == 64
    der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    key.public_key().verify(der, f"{header_b64}.{claims_b64}".encode(), ec.ECDSA(hashes.SHA256()))


# ---- key validation (loaded when the config is created) ----

def test_jwt_key_file_missing():
    with pytest.raises(ValueError, match="Unable to read private key file"):
        JWTBearerConfig(client_id="id", private_key_path="/nonexistent/key.pem")


def test_jwt_key_not_pem(rsa_key):
    with pytest.raises(ValueError, match="Unable to load private key"):
        JWTBearerConfig(client_id="id", private_key="not a key")


def test_jwt_encrypted_key(rsa_key):
    from cryptography.hazmat.primitives import serialization
    key, _ = rsa_key
    encrypted = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.BestAvailableEncryption(b"pw"))

    with pytest.raises(ValueError, match="private_key_password"):
        JWTBearerConfig(client_id="id", private_key=encrypted)
    with pytest.raises(ValueError, match="Unable to load private key"):
        JWTBearerConfig(client_id="id", private_key=encrypted, private_key_password="wrong")

    config = JWTBearerConfig(client_id="id", private_key=encrypted, private_key_password="pw")
    assert "pw" not in repr(config).replace("private_key_password", "")
    assert config.build_assertion(TOKEN_URL).count(".") == 2


def test_jwt_unneeded_password(rsa_key):
    with pytest.raises(ValueError, match="not encrypted"):
        JWTBearerConfig(client_id="id", private_key=rsa_key[1], private_key_password="pw")


def test_jwt_password_from_env(monkeypatch, rsa_key):
    from cryptography.hazmat.primitives import serialization
    encrypted = rsa_key[0].private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.BestAvailableEncryption(b"pw"))
    monkeypatch.setenv(auth.ENV_CLIENT_ID, "id")
    monkeypatch.setenv(auth.ENV_PRIVATE_KEY_BASE64, base64.b64encode(encrypted).decode())
    monkeypatch.setenv(auth.ENV_PRIVATE_KEY_PASSWORD, "pw")
    assert isinstance(OAuthConfig.from_env(), JWTBearerConfig)


def test_jwt_algorithm_key_mismatch(rsa_key, ec_key):
    with pytest.raises(ValueError, match="ES256 requires an EC"):
        JWTBearerConfig(client_id="id", private_key=rsa_key[1], algorithm="ES256")
    with pytest.raises(ValueError, match="RS256 requires an RSA"):
        JWTBearerConfig(client_id="id", private_key=ec_key[1], algorithm="RS256")


def test_jwt_wrong_curve():
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    key = ec.generate_private_key(ec.SECP384R1())
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    with pytest.raises(ValueError, match="P-256"):
        JWTBearerConfig(client_id="id", private_key=pem, algorithm="ES256")


def test_jwt_missing_cryptography(rsa_key):
    with patch.dict("sys.modules", {"cryptography": None, "cryptography.hazmat.primitives": None}):
        with pytest.raises(ImportError, match="oaaclient\\[jwt\\]"):
            JWTBearerConfig(client_id="id", private_key=rsa_key[1])


# ---- token_url must be https ----

def test_token_url_requires_https():
    with pytest.raises(ValueError, match="https"):
        ClientCredentialsConfig(client_id="id", client_secret="s", token_url="http://other.invalid/token")
    ClientCredentialsConfig(client_id="id", client_secret="s", token_url="https://other.invalid/token")


# ---- token request retries ----

def test_token_session_retries_post(monkeypatch):
    config = ClientCredentialsConfig(client_id="id", client_secret="s")
    client = make_client(config)
    token_retry = client._token_session.get_adapter(TOKEN_URL).max_retries
    shared_retry = client._http_adapter.get_adapter(TOKEN_URL).max_retries
    for status in (429, 500, 502, 503, 504):
        assert token_retry.is_retry("POST", status)
    # general API calls keep the default policy, POST pushes are not repeated on server errors
    assert not shared_retry.is_retry("POST", 503)
    assert shared_retry.is_retry("GET", 503)


def test_token_request_uses_token_session():
    config = ClientCredentialsConfig(client_id="id", client_secret="s")
    client = make_client(config)
    with patch.object(client._token_session, "post", return_value=token_response("via-token-session")) as post, \
         patch.object(client._http_adapter, "post") as shared_post:
        client._fetch_oauth_token()
    post.assert_called_once()
    shared_post.assert_not_called()
    assert client.api_key == "via-token-session"


def test_token_session_retries_server_errors(monkeypatch):
    """real HTTP round trip: two 503 responses then success"""
    monkeypatch.setattr(OAAClient, "DEFAULT_RETRY_BACKOFF_FACTOR", 0)
    responses = [503, 429, 200]
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            status = responses[len(seen)]
            seen.append(status)
            body = json.dumps({"access_token": "t", "expires_in": 60} if status == 200 else {"error": "busy"}).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = make_client(ClientCredentialsConfig(client_id="id", client_secret="s"))
        client._token_session.trust_env = False
        response = client._token_session.post(f"http://127.0.0.1:{server.server_port}/oauth/token", data={"a": "b"}, timeout=10)
    finally:
        server.shutdown()
        server.server_close()
    assert response.status_code == 200
    assert seen == [503, 429, 200]


@pytest.mark.parametrize("error", [
    requests.exceptions.ConnectionError("connection refused"),
    requests.exceptions.Timeout("timed out"),
    requests.exceptions.RetryError("too many 503 error responses"),
])
def test_token_connection_error(error):
    config = ClientCredentialsConfig(client_id="id", client_secret="s")
    client = make_client(config)
    with patch.object(client._token_session, "post", side_effect=error):
        with pytest.raises(OAAConnectionError):
            client._fetch_oauth_token()


def test_token_connection_error_at_startup():
    config = ClientCredentialsConfig(client_id="id", client_secret="s")
    with patch.object(OAAClient, "_test_connection"), \
         patch("requests.Session.post", side_effect=requests.exceptions.ConnectionError("connection refused")):
        with pytest.raises(OAAConnectionError):
            OAAClient(URL, oauth_config=config)


# ---- token response handling ----

@pytest.mark.parametrize("status", [200, 502])
def test_token_response_not_object(status):
    config = ClientCredentialsConfig(client_id="id", client_secret="s")
    with pytest.raises(OAAClientError if status == 200 else OAAResponseError) as exc:
        make_client(config, post=token_response(status=status, body=["unexpected", "list"]))
    assert exc.value.status_code == status


def test_token_response_string_body():
    config = ClientCredentialsConfig(client_id="id", client_secret="s")
    with pytest.raises(OAAResponseError):
        make_client(config, post=token_response(status=403, body="blocked"))


# ---- refresh margin, request signature, credential warning ----

def test_refresh_margin_capped_for_short_tokens():
    config = ClientCredentialsConfig(client_id="id", client_secret="s")
    client = make_client(config, post=token_response(expires_in=30))
    assert client._token_refresh_margin == 15
    with patch("requests.Session.post") as post:
        client._ensure_token()
    post.assert_not_called()

    client = make_client(config, post=token_response(expires_in=43200))
    assert client._token_refresh_margin == OAAClient.TOKEN_REFRESH_MARGIN


def test_perform_request_signature_unchanged():
    assert list(inspect.signature(OAAClient._perform_request).parameters) == ["self", "method", "api_path", "data", "params"]


def test_warn_when_api_key_and_oauth_env_set(monkeypatch, caplog):
    monkeypatch.setenv("VEZA_API_KEY", "envkey")
    monkeypatch.setenv(auth.ENV_CLIENT_ID, "id")
    with patch.object(OAAClient, "_test_connection"), caplog.at_level(logging.WARNING):
        OAAClient(URL)
    assert any(auth.ENV_CLIENT_ID in r.message for r in caplog.records)
    assert "envkey" not in caplog.text


def test_empty_api_key_env_falls_back_to_oauth(monkeypatch):
    monkeypatch.setenv("VEZA_API_KEY", "")
    monkeypatch.setenv(auth.ENV_CLIENT_ID, "id")
    monkeypatch.setenv(auth.ENV_CLIENT_SECRET, "secret")
    client = make_client()
    assert client.api_key == "tok-1"


def test_empty_api_key_env_without_oauth_raises(monkeypatch):
    monkeypatch.setenv("VEZA_API_KEY", "")
    with patch.object(OAAClient, "_test_connection"), pytest.raises(ValueError):
        OAAClient(URL)


def test_no_warning_when_api_key_env_empty(monkeypatch, caplog):
    monkeypatch.setenv("VEZA_API_KEY", "")
    monkeypatch.setenv(auth.ENV_CLIENT_ID, "id")
    monkeypatch.setenv(auth.ENV_CLIENT_SECRET, "secret")
    with caplog.at_level(logging.WARNING):
        make_client()
    assert "Both VEZA_API_KEY" not in caplog.text


# ---- client behavior ----

def test_client_oauth_fetches_token():
    config = ClientCredentialsConfig(client_id="id", client_secret="secret")
    with patch.object(OAAClient, "_test_connection"), patch("requests.Session.post", return_value=token_response("abc")) as post:
        client = OAAClient(URL, oauth_config=config)
    assert client.api_key == "abc"
    args, kwargs = post.call_args
    assert args[0] == TOKEN_URL
    assert kwargs["data"]["client_id"] == "id"


def test_client_oauth_from_env(monkeypatch):
    monkeypatch.setenv(auth.ENV_CLIENT_ID, "id")
    monkeypatch.setenv(auth.ENV_CLIENT_SECRET, "secret")
    client = make_client()
    assert client.api_key == "tok-1"


def test_api_key_unchanged():
    with patch.object(OAAClient, "_test_connection"), patch("requests.Session.post") as post:
        client = OAAClient(URL, "mykey")
        legacy = OAAClient(URL, token="legacy")
    assert (client.api_key, legacy.api_key) == ("mykey", "legacy")
    post.assert_not_called()


def test_api_key_env_wins_over_oauth_env(monkeypatch):
    monkeypatch.setenv("VEZA_API_KEY", "envkey")
    monkeypatch.setenv(auth.ENV_CLIENT_ID, "id")
    monkeypatch.setenv(auth.ENV_CLIENT_SECRET, "secret")
    with patch.object(OAAClient, "_test_connection"), patch("requests.Session.post") as post:
        client = OAAClient(URL)
    assert client.api_key == "envkey"
    post.assert_not_called()


def test_conflicting_credentials():
    config = ClientCredentialsConfig(client_id="id", client_secret="secret")
    with pytest.raises(ValueError):
        OAAClient(URL, api_key="k", oauth_config=config)
    with pytest.raises(ValueError):
        OAAClient(URL, token="k", oauth_config=config)


def test_no_credentials():
    with pytest.raises(ValueError):
        OAAClient(URL)


def test_token_endpoint_error():
    config = ClientCredentialsConfig(client_id="id", client_secret="bad")
    bad = token_response(status=401, body={"error": "invalid_client", "error_description": "bad secret"})
    with pytest.raises(OAAResponseError) as exc:
        make_client(config, post=bad)
    assert exc.value.status_code == 401
    assert "bad secret" in exc.value.message


def test_token_response_missing_token():
    config = ClientCredentialsConfig(client_id="id", client_secret="s")
    with pytest.raises(OAAClientError, match="access_token"):
        make_client(config, post=token_response(body={"token_type": "Bearer"}))


def test_proactive_refresh():
    config = ClientCredentialsConfig(client_id="id", client_secret="s")
    client = make_client(config, post=token_response("first", expires_in=3600))
    with patch("requests.Session.post", return_value=token_response("second")) as post:
        client._ensure_token()
        post.assert_not_called()
        # move inside the refresh margin
        client._token_expires_at -= 3600
        client._ensure_token()
        post.assert_called_once()
    assert client.api_key == "second"


def test_request_refreshes_expired_token_first():
    """_perform_request itself triggers the proactive refresh, before the API call is sent"""
    config = ClientCredentialsConfig(client_id="id", client_secret="s")
    client = make_client(config, post=token_response("old", expires_in=3600))
    client._token_expires_at = time.monotonic() - 1
    calls = []
    with patch("requests.Session.post", side_effect=lambda *a, **k: calls.append("token") or token_response("fresh")), \
         patch.object(client._http_adapter, "request", side_effect=lambda *a, **k: calls.append("api") or api_response()) as req:
        client.api_get("/api/v1/test")
    assert calls == ["token", "api"]
    assert req.call_args.kwargs["headers"]["authorization"] == "Bearer fresh"


def test_request_does_not_refresh_valid_token():
    config = ClientCredentialsConfig(client_id="id", client_secret="s")
    client = make_client(config, post=token_response("current", expires_in=3600))
    with patch("requests.Session.post") as post, patch.object(client._http_adapter, "request", return_value=api_response()):
        client.api_get("/api/v1/test")
    post.assert_not_called()


def api_response(status=200, body=None):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status
    resp.json.return_value = body if body is not None else {"ok": True}
    resp.reason = "Unauthorized"
    resp.url = f"{URL}/api/v1/test"
    if status >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
    return resp


def test_request_uses_current_token_and_retries_on_401():
    config = ClientCredentialsConfig(client_id="id", client_secret="s")
    client = make_client(config, post=token_response("old"))
    with patch("requests.Session.post", return_value=token_response("new")) as post, \
         patch.object(client._http_adapter, "request", side_effect=[api_response(401, {"code": "UNAUTHENTICATED", "message": "expired"}), api_response()]) as req:
        assert client.api_get("/api/v1/test") == {"ok": True}
    assert post.call_count == 1
    assert req.call_count == 2
    first, second = (c.kwargs["headers"]["authorization"] for c in req.call_args_list)
    assert (first, second) == ("Bearer old", "Bearer new")


@pytest.mark.parametrize("body", [["unauthorized"], "unauthorized"], ids=["json-list", "json-string"])
def test_401_retry_with_non_object_error_body(body):
    config = ClientCredentialsConfig(client_id="id", client_secret="s")
    client = make_client(config, post=token_response("old"))
    with patch("requests.Session.post", return_value=token_response("new")) as post, \
         patch.object(client._http_adapter, "request", side_effect=[api_response(401, body), api_response()]) as req:
        assert client.api_get("/api/v1/test") == {"ok": True}
    assert post.call_count == 1
    assert req.call_count == 2


def test_401_retry_only_once():
    config = ClientCredentialsConfig(client_id="id", client_secret="s")
    client = make_client(config)
    unauthorized = {"code": "UNAUTHENTICATED", "message": "no"}
    with patch("requests.Session.post", return_value=token_response("new")), \
         patch.object(client._http_adapter, "request", side_effect=[api_response(401, unauthorized), api_response(401, unauthorized)]) as req:
        with pytest.raises(OAAResponseError) as exc:
            client.api_get("/api/v1/test")
    assert exc.value.status_code == 401
    assert req.call_count == 2


def test_api_key_401_not_retried():
    with patch.object(OAAClient, "_test_connection"):
        client = OAAClient(URL, "mykey")
    with patch.object(client._http_adapter, "request", return_value=api_response(401, {"code": "UNAUTHENTICATED", "message": "no"})) as req:
        with pytest.raises(OAAResponseError):
            client.api_get("/api/v1/test")
    assert req.call_count == 1


# ---- live tests, skipped unless a test host and OAuth credentials are configured ----
# PYTEST_VEZA_HOST plus the standard VEZA_OAUTH_CLIENT_ID and one of:
#   VEZA_OAUTH_CLIENT_SECRET      (client credentials flow)
#   VEZA_OAUTH_PRIVATE_KEY_PATH or VEZA_OAUTH_PRIVATE_KEY_BASE64   (JWT bearer flow, optional VEZA_OAUTH_KEY_ID)
# The values are read at import time, before the clean_env fixture clears them for the offline tests.
#
# By default tests for a flow skip when its credentials are missing. CI sets PYTEST_REQUIRE_LIVE_AUTH to a
# comma separated list of flows (`client_secret`, `jwt`) that must run, a missing credential then fails the test.

live_host = os.getenv("PYTEST_VEZA_HOST")
live_client_id = os.getenv(auth.ENV_CLIENT_ID)
live_secret = os.getenv(auth.ENV_CLIENT_SECRET)
live_key_path = os.getenv(auth.ENV_PRIVATE_KEY_PATH)
live_key_base64 = os.getenv(auth.ENV_PRIVATE_KEY_BASE64)
live_key_id = os.getenv(auth.ENV_KEY_ID)
required_flows = {f.strip() for f in os.getenv("PYTEST_REQUIRE_LIVE_AUTH", "").lower().split(",") if f.strip()}

secret_configured = bool(live_host and live_client_id and live_secret)
jwt_configured = bool(live_host and live_client_id and (live_key_path or live_key_base64))

requires_live_secret = pytest.mark.skipif(not secret_configured and "client_secret" not in required_flows, reason="Test host or OAuth client credentials are not configured")
requires_live_jwt = pytest.mark.skipif(not jwt_configured and "jwt" not in required_flows, reason="Test host or OAuth JWT key is not configured")


def live_config(flow: str) -> OAuthConfig:
    """OAuth configuration for a live flow, fails the test when a required flow is not configured"""
    if flow == "client_secret":
        if not secret_configured:
            pytest.fail(f"client_secret flow required but {auth.ENV_CLIENT_ID}, {auth.ENV_CLIENT_SECRET} or PYTEST_VEZA_HOST is not set")
        return ClientCredentialsConfig(client_id=live_client_id, client_secret=live_secret)
    if not jwt_configured:
        pytest.fail(f"jwt flow required but {auth.ENV_CLIENT_ID}, a private key or PYTEST_VEZA_HOST is not set")
    return JWTBearerConfig(client_id=live_client_id, private_key_path=live_key_path or None,
                           private_key_base64=None if live_key_path else live_key_base64, key_id=live_key_id)


@pytest.fixture
def live_secret_con():
    return OAAClient(live_host, oauth_config=live_config("client_secret"))


@requires_live_secret
def test_live_client_credentials(live_secret_con):
    assert live_secret_con.api_key
    assert isinstance(live_secret_con.get_provider_list(), list)


@requires_live_secret
def test_live_client_credentials_refresh(live_secret_con):
    """expired token is replaced transparently"""
    first_token = live_secret_con.api_key
    live_secret_con._token_expires_at = 0
    assert isinstance(live_secret_con.get_provider_list(), list)
    assert live_secret_con.api_key
    assert live_secret_con._token_expires_at > 0
    log.debug(f"token changed on refresh: {live_secret_con.api_key != first_token}")


@requires_live_secret
def test_live_revoked_token_retried(live_secret_con):
    """invalid token triggers a refresh and a successful retry"""
    live_secret_con.api_key = "not-a-valid-token"
    assert isinstance(live_secret_con.get_provider_list(), list)
    assert live_secret_con.api_key != "not-a-valid-token"


@requires_live_secret
def test_live_bad_secret():
    config = ClientCredentialsConfig(client_id=live_client_id, client_secret="invalid-secret")
    with pytest.raises(OAAResponseError) as exc:
        OAAClient(live_host, oauth_config=config)
    assert exc.value.status_code in (400, 401)


@requires_live_jwt
def test_live_jwt_bearer():
    con = OAAClient(live_host, oauth_config=live_config("jwt"))
    assert con.api_key
    assert isinstance(con.get_provider_list(), list)


# ---- complete push test for each OAuth flow ----

@pytest.fixture(scope="module", params=[
    pytest.param("client_secret", marks=requires_live_secret),
    pytest.param("jwt", marks=requires_live_jwt),
])
def veza_con(request):
    """Overrides the conftest `veza_con` for this module so `app_provider` and the push test run once per OAuth flow"""
    return OAAClient(live_host, oauth_config=live_config(request.param))


@pytest.mark.timeout(TEST_TIMEOUT)
def test_live_oauth_push(veza_con, app_provider):
    """Create a provider, push an application payload and wait for it to parse, authenticated with OAuth"""
    assert veza_con._oauth is not None
    app = generate_app()
    # replace any character not allowed in a data source name (e.g. "/", "[", "]")
    data_source_name = re.sub(r"[^ @#$%&*:()!,a-zA-Z0-9_'\"=.-]", "-", os.environ.get("PYTEST_CURRENT_TEST"))

    response = veza_con.push_application(app_provider["name"], data_source_name=data_source_name, application_object=app)
    assert response
    assert "warnings" in response

    while True:
        data_source = veza_con.get_data_source(data_source_name, provider_id=app_provider["id"])
        if data_source["status"] == "SUCCESS":
            break
        assert not FAILURE_REGEX.match(data_source["status"]), f"Datasource parsing failure: {data_source}"
        time.sleep(4)
