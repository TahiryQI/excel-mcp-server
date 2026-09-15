"""Liveness probe for the streamable HTTP transport.

A bare GET on /mcp is rejected by the MCP session manager (400/406), which is
exactly what we want: it proves the ASGI app is routing requests without
opening a session that would never be terminated. Only a connection error or
a timeout means the server is actually down.
"""

import os
import sys
import urllib.error
import urllib.request

host = "127.0.0.1"
port = os.environ.get("FASTMCP_PORT", "8017")
url = f"http://{host}:{port}/mcp"

try:
    urllib.request.urlopen(url, timeout=4)
except urllib.error.HTTPError:
    pass
except Exception as exc:
    print(f"unhealthy: {url}: {exc}", file=sys.stderr)
    sys.exit(1)
