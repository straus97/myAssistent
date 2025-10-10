from __future__ import annotations
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode, unquote
import re

_TRACK_KEYS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "gclid",
    "fbclid",
    "yclid",
    "mc_cid",
    "mc_eid",
    "_hsenc",
    "_hsmi",
    "ref",
    "ref_src",
    "spm",
    "igshid",
}


def canonicalize_url(url: str) -> str:
    if not url:
        return url
    u = urlparse(url.strip())
    scheme = (u.scheme or "https").lower()
    netloc = (u.netloc or "").lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]

    # аккуратный path
    path = unquote(u.path or "")
    path = re.sub(r"/{2,}", "/", path).rstrip("/")
    # чистим query
    q_pairs = [(k, v) for (k, v) in parse_qsl(u.query, keep_blank_values=False) if k.lower() not in _TRACK_KEYS]
    q_pairs.sort()
    query = urlencode(q_pairs)

    # убираем фрагмент
    frag = ""
    can = urlunparse((scheme, netloc, path, "", query, frag))
    return can
