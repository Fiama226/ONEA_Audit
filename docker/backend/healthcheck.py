"""Container healthcheck: GET /api/v1/health/ on the local gunicorn.

Production settings redirect plain HTTP and validate the Host header, so the probe sends
X-Forwarded-Proto: https (as nginx does) and the first ALLOWED_HOSTS entry as Host.
"""

import os
import sys
import urllib.request

host = (os.environ.get("ALLOWED_HOSTS", "localhost").split(",")[0].strip() or "localhost").lstrip(
    "."
)
request = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/health/",
    headers={"Host": host, "X-Forwarded-Proto": "https"},
)
try:
    with urllib.request.urlopen(request, timeout=4) as response:  # noqa: S310
        sys.exit(0 if response.status == 200 else 1)
except Exception:
    sys.exit(1)
