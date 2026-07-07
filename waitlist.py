# -*- coding: utf-8 -*-
"""
구독 신청 (무료 뉴스레터 / 유료판 얼리버드 대기)
==============================================
무료: 매주 무료판 뉴스레터를 받을 구독자 명단(Brevo BREVO_FREE_LIST_ID).
유료 대기: 실제 결제 수단(Polar/Toss 등)을 붙이기 전, 결제 의향이 있는 방문자를 먼저 모은다
           (Brevo BREVO_WAITLIST_LIST_ID) — 결제/코드 발급 없음.

반환값은 (성공여부, 상태코드) 이며, 실제 언어별 메시지는 호출부(app.py)가 i18n.t()로 렌더한다
— 이 모듈은 Streamlit 세션/언어에 의존하지 않는다.
"""
import re
from datetime import datetime, timezone

import brevo
import config

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match((email or "").strip()))


def join_free(email: str) -> tuple:
    """무료 뉴스레터 구독 신청. (True, "success_free") 또는 (False, 에러코드)."""
    email = (email or "").strip().lower()
    if not is_valid_email(email):
        return False, "invalid_email"

    key, list_id = config.brevo_api_key(), config.brevo_free_list_id()
    if not key or not list_id:
        return False, "not_configured"

    ok = brevo.add_contact_to_list(email, list_id, {
        "SOURCE": "dhandho-screener app free signup",
        "JOINED_AT": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }, key)
    return (True, "success_free") if ok else (False, "error")


def join_waitlist(email: str) -> tuple:
    """유료판 얼리버드 대기 신청. (True, "success_waitlist") 또는 (False, 에러코드)."""
    email = (email or "").strip().lower()
    if not is_valid_email(email):
        return False, "invalid_email"

    key, list_id = config.brevo_api_key(), config.brevo_waitlist_list_id()
    if not key or not list_id:
        return False, "not_configured"

    ok = brevo.add_contact_to_list(email, list_id, {
        "SOURCE": "dhandho-screener app waitlist",
        "EARLYBIRD": True,
        "JOINED_AT": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }, key)
    return (True, "success_waitlist") if ok else (False, "error")


def _notify_admin_ticker_request(email: str, ticker: str) -> None:
    """관리자(브레보 발신자 계정)에게 신규 종목 추가 요청 알림 메일 발송 — best-effort, 실패해도 사용자 흐름엔 영향 없음."""
    key = config.brevo_api_key()
    admin_email, sender_name = config.brevo_sender()
    if not key or not admin_email:
        return
    brevo.send_transactional_email(
        admin_email, sender_name, admin_email,
        f"[Dhandho Screener] 종목 추가 요청: {ticker}",
        f"<p>새 분석 대상 추가 요청이 접수됐습니다.</p><p><b>티커:</b> {ticker}<br><b>요청자 이메일:</b> {email}</p>",
        key,
    )


def request_ticker(email: str, ticker: str) -> tuple:
    """분석 유니버스에 없는 종목 추가 요청. (True, "success_universe_request") 또는 (False, 에러코드).
    성공 시 관리자에게 알림 메일도 best-effort 로 발송한다."""
    email = (email or "").strip().lower()
    ticker = (ticker or "").strip().upper()
    if not is_valid_email(email):
        return False, "invalid_email"
    if not ticker:
        return False, "error"

    key, list_id = config.brevo_api_key(), config.brevo_universe_list_id()
    if not key or not list_id:
        return False, "not_configured"

    ok = brevo.add_contact_to_list(email, list_id, {
        "SOURCE": "dhandho-screener app universe request",
        "REQUESTED_TICKER": ticker,
        "JOINED_AT": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }, key)
    if not ok:
        return False, "error"

    _notify_admin_ticker_request(email, ticker)
    return True, "success_universe_request"
