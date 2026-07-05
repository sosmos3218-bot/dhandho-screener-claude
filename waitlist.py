# -*- coding: utf-8 -*-
"""
구독 신청 (무료 뉴스레터 / 유료판 얼리버드 대기)
==============================================
무료: 매주 무료판 뉴스레터를 받을 구독자 명단(Brevo BREVO_FREE_LIST_ID).
유료 대기: 실제 결제 수단(Polar/Toss 등)을 붙이기 전, 결제 의향이 있는 방문자를 먼저 모은다
           (Brevo BREVO_WAITLIST_LIST_ID) — 결제/코드 발급 없음.
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
    """무료 뉴스레터 구독 신청. 성공 시 (True, 안내메시지), 실패 시 (False, 에러메시지)."""
    email = (email or "").strip().lower()
    if not is_valid_email(email):
        return False, "이메일 형식을 확인해 주세요."

    list_id = config.brevo_free_list_id()
    if not config.brevo_api_key() or not list_id:
        return False, "구독 신청이 아직 준비 중입니다. 잠시 후 다시 시도해 주세요."

    ok = _add_to_brevo_list(email, list_id, {
        "SOURCE": "dhandho-screener app free signup",
        "JOINED_AT": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    if not ok:
        return False, "등록 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."
    return True, "무료 뉴스레터 구독이 완료되었습니다 — 매주 새 스크리닝 결과를 보내드립니다."


def join_waitlist(email: str) -> tuple:
    """유료판 얼리버드 대기 신청. 성공 시 (True, 안내메시지), 실패 시 (False, 에러메시지)."""
    email = (email or "").strip().lower()
    if not is_valid_email(email):
        return False, "이메일 형식을 확인해 주세요."

    list_id = config.brevo_waitlist_list_id()
    if not config.brevo_api_key() or not list_id:
        return False, "대기자 등록이 아직 준비 중입니다. 잠시 후 다시 시도해 주세요."

    ok = _add_to_brevo_list(email, list_id, {
        "SOURCE": "dhandho-screener app waitlist",
        "EARLYBIRD": True,
        "JOINED_AT": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    if not ok:
        return False, "등록 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."
    return True, "얼리버드 대기자로 등록되었습니다 — 유료판 출시 시 평생 할인가로 안내드립니다."
