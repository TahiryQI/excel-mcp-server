import os
import sys
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_REPO_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from starlette.testclient import TestClient  # noqa: E402

import excel_mcp.server as server  # noqa: E402

_REDIRECT_STATUSES = (301, 302, 303, 307, 308)

_INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test-client", "version": "1.0"},
    },
}

_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


class TestStreamableHttpPath(unittest.TestCase):
    """Clients whose HTTP stack does not follow redirects (e.g. Spring AI's
    HttpClientStreamableHttpTransport, built on the JDK HttpClient) must be able
    to handshake on /mcp as well as on /mcp/.

    The session manager can only be started once per FastMCP instance, so the
    whole class shares a single app and client.
    """

    @classmethod
    def setUpClass(cls):
        cls._client_cm = TestClient(server.build_streamable_http_app(), follow_redirects=False)
        cls.client = cls._client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_cm.__exit__(None, None, None)

    def _post_initialize(self, path):
        return self.client.post(path, json=_INITIALIZE, headers=_HEADERS, timeout=10)

    def test_initialize_without_trailing_slash_is_not_redirected(self):
        response = self._post_initialize("/mcp")
        self.assertNotIn(
            response.status_code,
            _REDIRECT_STATUSES,
            f"/mcp answered {response.status_code} -> {response.headers.get('location')}",
        )
        self.assertEqual(response.status_code, 200)

    def test_initialize_with_trailing_slash_still_works(self):
        response = self._post_initialize("/mcp/")
        self.assertEqual(response.status_code, 200)

    def test_unrelated_paths_are_not_captured(self):
        response = self.client.post("/not-mcp", json=_INITIALIZE, headers=_HEADERS, timeout=10)
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
