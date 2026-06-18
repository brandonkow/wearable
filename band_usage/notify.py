"""Push a notification to a phone (and thus the band) via ntfy.

ntfy (https://ntfy.sh) is a free, open-source pub/sub notification service.
Install the ntfy Android app, subscribe to a private topic name, and this
posts to it. The notification appears on the phone and mirrors to the Fit 3.
"""

from __future__ import annotations

from typing import List, Optional
from urllib import error, request


def send_ntfy(
    server: str,
    topic: str,
    title: str,
    message: str,
    token: Optional[str] = None,
    priority: str = "default",
    tags: Optional[List[str]] = None,
    timeout: int = 15,
) -> int:
    """POST a message to an ntfy topic. Returns the HTTP status code.

    Raises ``ValueError`` if no topic is configured.
    """
    if not topic:
        raise ValueError("No ntfy topic configured (set ntfy.topic or NTFY_TOPIC).")

    url = f"{server.rstrip('/')}/{topic}"
    req = request.Request(url, data=message.encode("utf-8"), method="POST")
    # Title goes in a header, which must be latin-1 safe -> keep it ASCII.
    req.add_header("Title", title.encode("ascii", "ignore").decode("ascii"))
    req.add_header("Priority", priority)
    if tags:
        req.add_header("Tags", ",".join(tags))
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except error.HTTPError as exc:
        raise RuntimeError(f"ntfy returned HTTP {exc.code}: {exc.reason}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Could not reach ntfy server {url}: {exc.reason}") from exc
