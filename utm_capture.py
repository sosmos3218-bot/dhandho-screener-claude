# -*- coding: utf-8 -*-
"""랜딩 URL 의 UTM 을 첫 유입 기준으로 세션과 쿠키에 남긴다.

Streamlit 은 한 페이지 앱이라, 유입 URL 로 들어온 뒤 필터/언어/다른 섹션에서
가입해도 쿼리가 사라질 수 있다. 이번 방문은 session_state, 다음 방문은
쿠키(dhandho_utm, attribution.UTM_COOKIE_DAYS)에 첫 UTM 만 유지한다.

CookieManager 의 기본 반환값 {} 는 '아직 브라우저 응답 전'과 '쿠키 없음'을
구분하지 못한다. 기본값을 None 으로 두어, 로드 전에 쿠키를 덮어쓰지 않는다.
"""
import datetime as dt

import streamlit as st
from extra_streamlit_components.CookieManager import CookieManager, _component_func

import attribution

UTM_COOKIE = "dhandho_utm"
SESSION_KEY = "utm_first_touch"
PERSISTED_KEY = "_utm_persisted_token"


class NullableCookieManager(CookieManager):
    """getAll 이 오기 전에는 cookies 가 None 이다. 빈 dict 와 구분된다."""

    def __init__(self, key: str = "dhandho_cookie_manager"):
        self.cookie_manager = _component_func
        self.cookies = self.cookie_manager(method="getAll", key=key, default=None)

    def get(self, cookie: str):
        self._remove_extra_spacing()
        if not isinstance(self.cookies, dict):
            return None
        return self.cookies.get(cookie)

    def set(self, cookie, val, key="set", **kwargs):
        # 브라우저 응답 전에 set 이 호출돼도 None 에 대입하며 죽지 않게 한다.
        # 다음 실행의 getAll 이 self.cookies 를 다시 채우므로 여기 대입은 그 런에만 있다.
        if not isinstance(self.cookies, dict):
            self.cookies = {}
        return super().set(cookie, val, key=key, **kwargs)

    def delete(self, cookie, key="delete"):
        if not isinstance(self.cookies, dict):
            self.cookies = {}
        if cookie not in self.cookies:
            self.cookie_manager(method="delete", cookie=cookie, key=key, default=False)
            return
        super().delete(cookie, key=key)


def remember_first_touch(cookie_manager, query_params) -> dict:
    """현재 확정(또는 잠정) UTM 을 세션에 저장하고, 필요하면 쿠키에 한 번 쓴다."""
    cookie_manager._remove_extra_spacing()
    incoming = attribution.parse_utm_params(query_params)
    loaded = isinstance(cookie_manager.cookies, dict)
    stored = attribution.decode_utm_cookie(cookie_manager.get(UTM_COOKIE)) if loaded else {}
    session_utm = st.session_state.get(SESSION_KEY) or {}
    chosen, should_persist = attribution.resolve_attribution(
        stored, session_utm, incoming, cookie_loaded=loaded,
    )
    st.session_state[SESSION_KEY] = chosen
    if should_persist:
        token = attribution.encode_utm_cookie(chosen)
        if st.session_state.get(PERSISTED_KEY) != token:
            cookie_manager.set(
                UTM_COOKIE,
                token,
                key="dhandho_utm_set",
                path="/",
                expires_at=dt.datetime.now() + dt.timedelta(days=attribution.UTM_COOKIE_DAYS),
                same_site="lax",
            )
            st.session_state[PERSISTED_KEY] = token
    return chosen


def current() -> dict:
    """가입 시점에 넘길 첫 유입 UTM. 없으면 빈 dict (SOURCE=direct)."""
    value = st.session_state.get(SESSION_KEY) or {}
    return dict(value)
