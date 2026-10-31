# -*- coding: utf-8 -*-
"""가입 경로(UTM) 파싱과 Brevo 컨택 속성 변환.

랜딩 URL의 utm_* 를 첫 유입 기준으로 유지한 뒤, 무료 구독/얼리버드 대기 신청 시
Brevo 컨택 속성으로 넘긴다. 이 모듈은 Streamlit 에 의존하지 않는다.

Brevo 는 스키마에 없는 속성을 조용히 버리므로, 아래 속성을 대시보드에서
만들거나 scripts/ensure_brevo_attributes.py 로 등록해야 실제로 저장된다.

  SOURCE        text   utm_source 값. 없으면 direct
  UTM_SOURCE    text
  UTM_MEDIUM    text
  UTM_CAMPAIGN  text
  UTM_CONTENT   text
  UTM_TERM      text

SOURCE 는 가입 채널용이다. 결제 웹훅과 관리자 수동 추가가 쓰는 SOURCE 문구
(예: admin manual add)는 이 모듈이 바꾸지 않는다.
"""
import json
from urllib.parse import parse_qsl, quote

# 쿠키에 첫 유입 UTM 을 남겨 두는 기간. 이 기간 안에 다른 페이지에서 가입해도
# 처음 본 캠페인이 유지된다.
UTM_COOKIE_DAYS = 90

UTM_FIELDS = ("source", "medium", "campaign", "content", "term")

UTM_QUERY_TO_FIELD = {
    "utm_source": "source",
    "utm_medium": "medium",
    "utm_campaign": "campaign",
    "utm_content": "content",
    "utm_term": "term",
}

# Brevo 컨택 속성 이름. 대시보드에 text 타입으로 있어야 한다.
BREVO_UTM_ATTRIBUTES = {
    "source": "UTM_SOURCE",
    "medium": "UTM_MEDIUM",
    "campaign": "UTM_CAMPAIGN",
    "content": "UTM_CONTENT",
    "term": "UTM_TERM",
}

_MAX_LEN = 100
_DROPPED_CHARS = set(";=<>\"'\\{}|")


def sanitize_utm_value(value) -> str:
    """UTM 값 하나를 속성/쿠키에 넣을 수 있는 짧은 문자열로 정리한다. 비면 빈 문자열."""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    if value is None:
        return ""
    chars = []
    for ch in str(value):
        if ch.isspace():
            chars.append(" ")
        elif ch.isprintable() and ch not in _DROPPED_CHARS:
            chars.append(ch)
    text = " ".join("".join(chars).split())
    return text[:_MAX_LEN]


def _clean(utm) -> dict:
    if not isinstance(utm, dict):
        return {}
    out = {}
    for field in UTM_FIELDS:
        val = sanitize_utm_value(utm.get(field))
        if val:
            out[field] = val
    return out


def _lookup_param(params, key: str):
    if params is None:
        return None
    get_all = getattr(params, "get_all", None)
    if callable(get_all):
        try:
            values = get_all(key)
        except Exception:
            values = None
        else:
            # get_all 이 있으면 빈 목록은 '그 키 없음'이다. dict.get 으로 넘어가지 않는다.
            return values[0] if values else None
    getter = getattr(params, "get", None)
    if callable(getter):
        return getter(key)
    return None


def parse_utm_params(params) -> dict:
    """쿼리 파라미터(dict 또는 st.query_params)에서 utm_* 만 골라 정리한다."""
    found = {}
    for query_key, field in UTM_QUERY_TO_FIELD.items():
        val = sanitize_utm_value(_lookup_param(params, query_key))
        if val:
            found[field] = val
    return found


def first_touch(stored, incoming) -> dict:
    """이미 저장된 유입이 있으면 그대로 두고, 없을 때만 incoming 을 쓴다."""
    stored = _clean(stored)
    if stored:
        return stored
    return _clean(incoming)


def resolve_attribution(stored_cookie, session_utm, incoming, *, cookie_loaded: bool) -> tuple:
    """(확정 UTM dict, 쿠키에 새로 써야 하는지) 를 반환한다.

    쿠키 저장소가 아직 브라우저에서 로드되기 전에는 쓰지 않는다.
    로드된 뒤에는 쿠키(이전 방문) > 이번 세션에 이미 본 값 > 현재 URL 순으로
    첫 유입을 고른다. 빈 유입(direct)은 쿠키로 잠그지 않아서, 이후 캠페인 링크가
    첫 UTM 으로 남을 수 있다.
    """
    stored_cookie = _clean(stored_cookie)
    session_utm = _clean(session_utm)
    incoming = _clean(incoming)
    if not cookie_loaded:
        return first_touch(session_utm, incoming), False
    chosen = first_touch(stored_cookie, first_touch(session_utm, incoming))
    should_persist = bool(chosen) and chosen != stored_cookie
    return chosen, should_persist


def encode_utm_cookie(utm) -> str:
    """쿠키 값. JSON 이 아니므로 쿠키 라이브러리가 객체로 다시 파싱하지 않는다."""
    clean = _clean(utm)
    parts = [
        f"{field}={quote(clean[field], safe='')}"
        for field in UTM_FIELDS
        if field in clean
    ]
    return "v1:" + "&".join(parts)


def decode_utm_cookie(raw) -> dict:
    """encode_utm_cookie 결과, JSON 문자열, 또는 이미 풀린 dict 를 받는다."""
    if isinstance(raw, dict):
        mapped = {}
        for field in UTM_FIELDS:
            if field in raw:
                mapped[field] = raw.get(field)
            elif f"utm_{field}" in raw:
                mapped[field] = raw.get(f"utm_{field}")
        return _clean(mapped)
    if not isinstance(raw, str):
        return {}
    text = raw.strip()
    if text.startswith("v1:"):
        return _clean(dict(parse_qsl(text[3:], keep_blank_values=False)))
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except Exception:
            return {}
        return decode_utm_cookie(data)
    return {}


def brevo_signup_attributes(utm, *, joined_at: str, extra: dict = None) -> dict:
    """무료/대기 가입에 실어 보낼 Brevo 속성.

    UTM_* 는 값이 있을 때만 넣는다. 빈 문자열로 기존 값을 지우지 않기 위해서다.
    SOURCE 는 utm_source 또는 'direct'.
    """
    clean = _clean(utm)
    attrs = {
        "SOURCE": clean.get("source") or "direct",
        "JOINED_AT": joined_at,
    }
    for field, name in BREVO_UTM_ATTRIBUTES.items():
        if clean.get(field):
            attrs[name] = clean[field]
    if extra:
        attrs.update(extra)
    return attrs
