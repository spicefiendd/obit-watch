"""HTTP helpers using urllib only."""

from __future__ import annotations

import ssl
import urllib.error
import urllib.request
from typing import Optional, Tuple

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


def fetch(
    url: str,
    timeout: float = 15.0,
    *,
    accept: Optional[str] = None,
) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """
    GET url. Returns (body_text, http_code, error_reason).

    On success: (text, code, None)
    On HTTP error with body: (text_or_None, code, reason)
    On network/other: (None, None, reason)
    """
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": accept
        or "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            code = getattr(resp, "status", None) or resp.getcode()
            raw = resp.read()
            charset = "utf-8"
            ctype = resp.headers.get_content_charset()
            if ctype:
                charset = ctype
            try:
                text = raw.decode(charset, errors="replace")
            except Exception:
                text = raw.decode("utf-8", errors="replace")
            return text, int(code), None
    except urllib.error.HTTPError as e:
        body = None
        try:
            raw = e.read()
            body = raw.decode("utf-8", errors="replace") if raw else None
        except Exception:
            body = None
        return body, int(e.code), str(e.reason or e)
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", None) or str(e)
        return None, None, str(reason)
    except Exception as e:
        return None, None, str(e)


def is_blocked_code(code: Optional[int]) -> bool:
    return code in (401, 403, 429, 451)
