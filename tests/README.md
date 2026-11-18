# OAA Client Tests

## Running tests

Tests are managed by `pytest` and can be run locally by installing the package along with the test dependencies.

```
python3 -m venv venv
pip install -e ".[test]"
```

To run the tests invoke the `pytest` command

### Testing with a Veza instance

By default the tests all run stand-alone and do not require a Veza instance to connect to.

To run the complete tests, which include pushing a payload to Veza, set the OS environment variables `PYTEST_VEZA_HOST` and `VEZA_API_KEY` with the hostname and API key respectively.

> If testing with a local instance of Veza using unsigned certificates set `VEZA_UNSAFE_HTTPS=true`

### Test Timeouts

Tests validate Veza parsing after OAA push have a default timeout. If the data source does not change from the pending
state within the timeout the test will fail. The timeout can be over-ridden with the OS environment variable
`OAA_PUSH_TIMEOUT` which is a number in seconds for the timeout.

OAuth live tests in `test_oauth.py` require `PYTEST_VEZA_HOST` plus the standard client variables `VEZA_OAUTH_CLIENT_ID` and either `VEZA_OAUTH_CLIENT_SECRET` (client credentials) or `VEZA_OAUTH_PRIVATE_KEY_PATH` / `VEZA_OAUTH_PRIVATE_KEY_BASE64` (JWT bearer, key file path or base64 encoded PEM, optional `VEZA_OAUTH_KEY_ID`). Tests for a flow are skipped when its credentials are not set.

`test_oauth.py` includes a full push test that runs once for each OAuth flow that is configured. By default a flow without credentials is skipped; set `PYTEST_REQUIRE_LIVE_AUTH` to `client_secret`, `jwt` or both (comma separated) to make a missing flow fail instead, e.g. in CI.
