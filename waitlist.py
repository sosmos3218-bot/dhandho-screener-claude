# -*- coding: utf-8 -*-
"""
구독 신청 (무료 뉴스레터 / 유료판 얼리버드 대기)
==============================================
무료: 매주 무료판 뉴스레터를 받을 구독자 명단(Brevo BREVO_FREE_LIST_ID).
유료 대기: 결제 수단을 붙이기 전 관심 등록만 받는다(Brevo BREVO_WAITLIST_LIST_ID).
           config.paid_promo_enabled() 가 켜져 있을 때만 받는다. 기본은 꺼짐.

가입 시 UTM(utm 인자)은 attribution.brevo_signup_attributes() 로
SOURCE(utm_source 또는 direct)와 UTM_* 속성에 실린다.

반환값은 (성공여부, 상태코드) 이며, 실제 언어별 메시지는 호출부(app.py)가 i18n.t()로 렌더한다.
이 모듈은 Streamlit 세션/언어에 의존하지 않는다.
"""
import html
import re
from datetime import datetime, timezone

import attribution
import brevo
import config
import privacy

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match((email or "").strip()))


def _joined_at() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _store_contact(email: str, list_id: str, attributes: dict, key: str) -> bool:
    """DOI 템플릿과 리다이렉트 URL 이 둘 다 있으면 double opt-in, 아니면 바로 리스트에 넣는다.

    Brevo DOI 는 redirectionUrl 이 필수다. 템플릿 ID 만 있고 URL 이 없으면
    가입이 실패하지 않도록 기존 단일 옵트인으로 보낸다.
    """
    template_id = config.brevo_doi_template_id()
    redirect = config.brevo_doi_redirect_url()
    if template_id and redirect:
        return brevo.create_double_optin_contact(
            email, list_id, attributes, template_id, redirect, key)
    return brevo.add_contact_to_list(email, list_id, attributes, key)


def _signup_attributes(utm, extra: dict = None) -> dict:
    joined = _joined_at()
    fields = {
        "CONSENT_AT": joined,
        "CONSENT_VERSION": privacy.POLICY_VERSION,
    }
    if extra:
        fields.update(extra)
    return attribution.brevo_signup_attributes(utm, joined_at=joined, extra=fields)


def join_free(email: str, utm: dict = None, consent: bool = False) -> tuple:
    """무료 뉴스레터 구독 신청. (True, "success_free") 또는 (False, 에러코드).

    utm 은 attribution.parse_utm_params() 결과(source/medium/campaign/...).
    없으면 SOURCE=direct. consent 가 없으면 Brevo 에 쓰지 않는다.
    """
    if not consent:
        return False, "consent_required"
    email = (email or "").strip().lower()
    if not is_valid_email(email):
        return False, "invalid_email"

    key, list_id = config.brevo_api_key(), config.brevo_free_list_id()
    if not key or not list_id:
        return False, "not_configured"

    ok = _store_contact(email, list_id, _signup_attributes(utm), key)
    return (True, "success_free") if ok else (False, "error")


def join_waitlist(email: str, utm: dict = None, consent: bool = False) -> tuple:
    """유료판 얼리버드 대기 신청. (True, "success_waitlist") 또는 (False, 에러코드).

    유료 홍보가 꺼져 있으면 Brevo 에 쓰지 않고 promo_disabled 를 반환한다.
    """
    if not consent:
        return False, "consent_required"
    if not config.paid_promo_enabled():
        return False, "promo_disabled"

    email = (email or "").strip().lower()
    if not is_valid_email(email):
        return False, "invalid_email"

    key, list_id = config.brevo_api_key(), config.brevo_waitlist_list_id()
    if not key or not list_id:
        return False, "not_configured"

    ok = _store_contact(
        email, list_id, _signup_attributes(utm, extra={"EARLYBIRD": True}), key)
    return (True, "success_waitlist") if ok else (False, "error")


def _notify_admin_ticker_request(email: str, ticker: str) -> None:
    """관리자에게 신규 종목 추가 요청 알림. 실패해도 사용자 흐름에는 영향 없음."""
    key = config.brevo_api_key()
    admin_email, sender_name = config.brevo_sender()
    if not key or not admin_email:
        return
    safe_ticker = html.escape(ticker or "", quote=True)
    safe_email = html.escape(email or "", quote=True)
    brevo.send_transactional_email(
        admin_email, sender_name, admin_email,
        f"[Dhandho Screener] 종목 추가 요청: {safe_ticker}",
        "<p>새 분석 대상 추가 요청이 접수됐습니다.</p>"
        f"<p><b>티커:</b> {safe_ticker}<br><b>요청자 이메일:</b> {safe_email}</p>",
        key,
    )


def request_ticker(email: str, ticker: str, consent: bool = False) -> tuple:
    """분석 유니버스에 없는 종목 추가 요청. (True, "success_universe_request") 또는 (False, 에러코드).
    성공 시 관리자에게 알림 메일도 best-effort 로 발송한다."""
    if not consent:
        return False, "consent_required"
    email = (email or "").strip().lower()
    ticker = (ticker or "").strip().upper()
    if not is_valid_email(email):
        return False, "invalid_email"
    if not ticker:
        return False, "error"

    key, list_id = config.brevo_api_key(), config.brevo_universe_list_id()
    if not key or not list_id:
        return False, "not_configured"

    joined = _joined_at()
    ok = brevo.add_contact_to_list(email, list_id, {
        "SOURCE": "dhandho-screener app universe request",
        "REQUESTED_TICKER": ticker,
        "JOINED_AT": joined,
        "CONSENT_AT": joined,
        "CONSENT_VERSION": privacy.POLICY_VERSION,
    }, key)
    if not ok:
        return False, "error"

    _notify_admin_ticker_request(email, ticker)
    return True, "success_universe_request"
