"""Default and extra obituary source checkers (stdlib HTTP only)."""

from __future__ import annotations

import re
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from .httputil import fetch, is_blocked_code
from .match import plausible_hit


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _result(
    sid: str,
    name: str,
    url: str,
    status: str,
    http_code: Optional[int],
    excerpt: Optional[str],
    *,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "id": sid,
        "name": name,
        "url": url,
        "status": status,
        "http_code": http_code,
        "excerpt": excerpt,
        "checked_at": _utc_now(),
    }
    if reason:
        out["reason"] = reason
    return out


def _status_from_fetch(
    body: Optional[str],
    code: Optional[int],
    err: Optional[str],
    names: Sequence[str],
) -> tuple:
    """Return (status, excerpt, reason)."""
    if code is not None and is_blocked_code(code):
        return "blocked", None, err or f"HTTP {code}"
    if err and body is None and code is None:
        return "error", None, err
    if code is not None and code >= 400 and not body:
        if is_blocked_code(code):
            return "blocked", None, err or f"HTTP {code}"
        return "error", None, err or f"HTTP {code}"
    if body is None:
        return "error", None, err or "empty response"
    excerpt = plausible_hit(body, names)
    if excerpt:
        return "hit", excerpt, None
    # HTTP error with body but no match
    if code is not None and code >= 400:
        return "error", None, err or f"HTTP {code}"
    return "miss", None, None


def _all_names(names: Sequence[str], variants: Sequence[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for n in list(names) + list(variants):
        n = (n or "").strip()
        key = n.lower()
        if n and key not in seen:
            seen.add(key)
            out.append(n)
    return out


def check_google_news_rss(
    names: Sequence[str],
    variants: Sequence[str],
    towns: Sequence[str],
    state: str,
    timeout: float,
) -> Dict[str, Any]:
    all_n = _all_names(names, variants)
    # Build query: ("Name1" OR "Name2") (obituary OR funeral) (Town1 OR Town2) STATE
    name_parts = " OR ".join(f'"{n}"' for n in all_n)
    loc_parts = " OR ".join(towns) if towns else ""
    q_bits = [f"({name_parts})", "(obituary OR funeral)"]
    if loc_parts:
        q_bits.append(f"({loc_parts})")
    if state:
        q_bits.append(state)
    q = " ".join(q_bits)
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"}
    )
    body, code, err = fetch(url, timeout=timeout, accept="application/rss+xml,application/xml,text/xml,*/*")
    status, excerpt, reason = _status_from_fetch(body, code, err, all_n)
    return _result("google-news-rss", "Google News RSS", url, status, code, excerpt, reason=reason)


def check_echovita(
    names: Sequence[str],
    variants: Sequence[str],
    towns: Sequence[str],
    state: str,
    timeout: float,
) -> Dict[str, Any]:
    all_n = _all_names(names, variants)
    st = (state or "IN").lower()
    # Prefer Plymouth / Culver listing pages; also try search
    candidate_urls = [
        f"https://www.echovita.com/us/{st}/plymouth/obituaries",
        f"https://www.echovita.com/us/{st}/culver/obituaries",
        "https://www.echovita.com/obituaries?q="
        + urllib.parse.quote(all_n[0] if all_n else "obituary"),
    ]
    # Dedupe and filter by requested towns if given
    town_l = {t.lower() for t in towns}
    urls: List[str] = []
    for u in candidate_urls:
        if "/plymouth/" in u and town_l and "plymouth" not in town_l:
            continue
        if "/culver/" in u and town_l and "culver" not in town_l:
            continue
        urls.append(u)
    if not urls:
        urls = candidate_urls

    last = None
    combined_body = []
    last_code = None
    last_err = None
    last_url = urls[0]
    for u in urls:
        body, code, err = fetch(u, timeout=timeout)
        last_url = u
        last_code = code
        last_err = err
        if code is not None and is_blocked_code(code):
            return _result(
                "echovita",
                "Echovita",
                u,
                "blocked",
                code,
                None,
                reason=err or f"HTTP {code}",
            )
        if body:
            combined_body.append(body)
            excerpt = plausible_hit(body, all_n)
            if excerpt:
                return _result("echovita", "Echovita", u, "hit", code, excerpt)
        last = (body, code, err)

    body = "\n".join(combined_body) if combined_body else None
    status, excerpt, reason = _status_from_fetch(body, last_code, last_err, all_n)
    return _result("echovita", "Echovita", last_url, status, last_code, excerpt, reason=reason)


def check_legacy(
    names: Sequence[str],
    variants: Sequence[str],
    state: str,
    timeout: float,
) -> Dict[str, Any]:
    all_n = _all_names(names, variants)
    primary = all_n[0] if all_n else ""
    # Legacy public search — may redirect / block scrapers
    params = {
        "first": "",
        "last": "",
        "country": "1",  # USA-ish; site varies
        "daterange": "Last1year",
        "state": state or "Indiana",
        "keyword": primary,
    }
    # Prefer keyword search URL which is more stable publicly
    url = "https://www.legacy.com/obituaries/search?" + urllib.parse.urlencode(
        {
            "countryId": "1",
            "stateId": "16",  # Indiana (legacy internal id; may drift)
            "dateRange": "last1year",
            "keyword": primary,
        }
    )
    body, code, err = fetch(url, timeout=timeout)
    if code is None and err:
        return _result(
            "legacy",
            "Legacy.com",
            url,
            "error",
            None,
            None,
            reason=f"Legacy search unreachable: {err}",
        )
    if code is not None and is_blocked_code(code):
        return _result(
            "legacy",
            "Legacy.com",
            url,
            "blocked",
            code,
            None,
            reason=err or f"HTTP {code}",
        )
    # Some Legacy pages require JS; if we got a thin shell, note error
    if body and len(body) < 500 and "legacy" in (body.lower()):
        return _result(
            "legacy",
            "Legacy.com",
            url,
            "error",
            code,
            None,
            reason="response too thin (likely JS-rendered)",
        )
    status, excerpt, reason = _status_from_fetch(body, code, err, all_n)
    if status == "error" and not reason:
        reason = "Legacy public search not workable"
    return _result("legacy", "Legacy.com", url, status, code, excerpt, reason=reason)


def check_findagrave(
    names: Sequence[str],
    variants: Sequence[str],
    towns: Sequence[str],
    state: str,
    timeout: float,
) -> Dict[str, Any]:
    all_n = _all_names(names, variants)
    primary = all_n[0] if all_n else ""
    parts = primary.split()
    first = parts[0] if parts else ""
    last = parts[-1] if len(parts) > 1 else ""
    params = {
        "firstname": first,
        "lastname": last,
        "location": state or "Indiana",
        "orderby": "r",
    }
    if towns:
        params["locationTownName"] = towns[0]
    url = "https://www.findagrave.com/memorial/search?" + urllib.parse.urlencode(params)
    body, code, err = fetch(url, timeout=timeout)
    status, excerpt, reason = _status_from_fetch(body, code, err, all_n)
    return _result("findagrave", "Find A Grave", url, status, code, excerpt, reason=reason)


def check_inkfree(
    names: Sequence[str],
    variants: Sequence[str],
    timeout: float,
) -> Dict[str, Any]:
    all_n = _all_names(names, variants)
    urls = [
        "https://www.inkfree.com/obituaries/",
        "https://www.inkfree.com/category/obituaries/",
        "https://www.thepilotnews.com/obituaries/",
    ]
    last_url = urls[0]
    last_code = None
    last_err = None
    combined = []
    for u in urls:
        body, code, err = fetch(u, timeout=timeout)
        last_url, last_code, last_err = u, code, err
        if code is not None and is_blocked_code(code):
            return _result(
                "inkfree",
                "InkFree / Marshall County news obituaries",
                u,
                "blocked",
                code,
                None,
                reason=err or f"HTTP {code}",
            )
        if body:
            combined.append(body)
            excerpt = plausible_hit(body, all_n)
            if excerpt:
                return _result(
                    "inkfree",
                    "InkFree / Marshall County news obituaries",
                    u,
                    "hit",
                    code,
                    excerpt,
                )
    body = "\n".join(combined) if combined else None
    status, excerpt, reason = _status_from_fetch(body, last_code, last_err, all_n)
    return _result(
        "inkfree",
        "InkFree / Marshall County news obituaries",
        last_url,
        status,
        last_code,
        excerpt,
        reason=reason,
    )


def check_funeral_homes(
    names: Sequence[str],
    variants: Sequence[str],
    timeout: float,
) -> List[Dict[str, Any]]:
    all_n = _all_names(names, variants)
    homes = [
        (
            "johnson-danielson",
            "Johnson-Danielson Funeral Home (Plymouth)",
            [
                "https://www.johnson-danielson.com/obituaries",
                "https://www.johnson-danielson.com/obituary",
                "https://www.johnson-danielson.com/",
            ],
        ),
        (
            "palmer-funeral",
            "Palmer Funeral Home (Marshall Co)",
            [
                "https://www.palmerfuneralhomes.com/obituary",
                "https://www.palmerfuneralhomes.com/obituaries",
                "https://www.palmerfuneralhomes.com/",
            ],
        ),
        (
            "odom-funeral",
            "Odom Funeral Home (Marshall Co)",
            [
                "https://www.odomfuneralhome.com/obituaries",
                "https://www.odomfuneralhome.com/obituary",
                "https://www.odomfuneralhome.com/",
            ],
        ),
    ]
    results: List[Dict[str, Any]] = []
    for sid, label, url_list in homes:
        last_url = url_list[0]
        last_code = None
        last_err = None
        hit = None
        blocked = None
        combined = []
        for u in url_list:
            body, code, err = fetch(u, timeout=timeout)
            last_url, last_code, last_err = u, code, err
            if code is not None and is_blocked_code(code):
                blocked = _result(
                    sid, label, u, "blocked", code, None, reason=err or f"HTTP {code}"
                )
                # Prefer blocked if all paths block; keep trying others first
                continue
            if body:
                combined.append(body)
                excerpt = plausible_hit(body, all_n)
                if excerpt:
                    hit = _result(sid, label, u, "hit", code, excerpt)
                    break
        if hit:
            results.append(hit)
        elif blocked and not combined:
            results.append(blocked)
        else:
            body = "\n".join(combined) if combined else None
            status, excerpt, reason = _status_from_fetch(body, last_code, last_err, all_n)
            if status == "error" and blocked:
                results.append(blocked)
            else:
                results.append(
                    _result(sid, label, last_url, status, last_code, excerpt, reason=reason)
                )
    return results


def check_extra_url(
    url: str,
    index: int,
    names: Sequence[str],
    variants: Sequence[str],
    timeout: float,
) -> Dict[str, Any]:
    all_n = _all_names(names, variants)
    body, code, err = fetch(url, timeout=timeout)
    status, excerpt, reason = _status_from_fetch(body, code, err, all_n)
    return _result(
        f"extra-{index}",
        f"Extra URL {index}",
        url,
        status,
        code,
        excerpt,
        reason=reason,
    )


def run_all_sources(
    *,
    names: Sequence[str],
    variants: Sequence[str],
    towns: Sequence[str],
    counties: Sequence[str],
    state: str,
    timeout: float,
    extra_urls: Sequence[str],
) -> List[Dict[str, Any]]:
    """Run every default source plus extras. Counties used only in query metadata / RSS context."""
    # Fold counties into town-like location boost for Google RSS
    loc_for_rss = list(towns) + list(counties)
    results: List[Dict[str, Any]] = []
    results.append(
        check_google_news_rss(names, variants, loc_for_rss, state, timeout)
    )
    results.append(check_echovita(names, variants, towns, state, timeout))
    results.append(check_legacy(names, variants, state, timeout))
    results.append(check_findagrave(names, variants, towns, state, timeout))
    results.append(check_inkfree(names, variants, timeout))
    results.extend(check_funeral_homes(names, variants, timeout))
    for i, u in enumerate(extra_urls, start=1):
        results.append(check_extra_url(u, i, names, variants, timeout))
    return results
