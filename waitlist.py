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
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

import config

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match((email or "").strip()))


def _add_to_brevo_list(email: str, list_id: str, attributes: dict) -> bool:
    key = config.brevo_api_key()
    if not key or not list_id:
        return False
    payload = {
        "email": email,
        "listIds": [int(list_id)],
        "updateEnabled": True,
        "attributes": attributes,
    }
    req = urllib.request.Request(
        "https://api.brevo.com/v3/contacts",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json", "api-key": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status in (201, 204)
    except urllib.error.HTTPError as e:
        return e.code == 204  # 이미 등록된 이메일(업데이트)도 정상 처리
    except Exception:
        return False


def join_free(email: str) -> tuple:
    """무료 뉴스레터 구독 신청. (True, "success_free") 또는 (False, 에러코드)."""
    email = (email or "").strip().lower()
    if not is_valid_email(email):
        return False, "invalid_email"

    list_id = config.brevo_free_list_id()
    if not config.brevo_api_key() or not list_id:
        return False, "not_configured"

    ok = _add_to_brevo_list(email, list_id, {
        "SOURCE": "dhandho-screener app free signup",
        "JOINED_AT": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    if not ok:
        return False, "error"
    return True, "success_free"


def join_waitlist(email: str) -> tuple:
    """유료판 얼리버드 대기 신청. (True, "success_waitlist") 또는 (False, 에러코드)."""
    email = (email or "").strip().lower()
    if not is_valid_email(email):
        return False, "invalid_email"

    list_id = config.brevo_waitlist_list_id()
    if not config.brevo_api_key() or not list_id:
        return False, "not_configured"

    ok = _add_to_brevo_list(email, list_id, {
        "SOURCE": "dhandho-screener app waitlist",
        "EARLYBIRD": True,
        "JOINED_AT": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    if not ok:
        return False, "error"
    return True, "success_waitlist"
