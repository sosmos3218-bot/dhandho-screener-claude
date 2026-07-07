# -*- coding: utf-8 -*-
"""
유료 구독 상태 확인 + 이메일 OTP 로그인
========================================
결제 자체는 Stripe Payment Link 가 처리하고, 결제 완료 웹훅(webhook/)이 구매자 이메일을
Brevo 유료 리스트(BREVO_PAID_LIST_ID)에 자동으로 추가한다. is_paid_email()은 그 리스트에
이메일이 있는지 조회만 한다 — 결제 로직은 이 저장소가 아니라 Cloudflare Worker(webhook/)에 있다.

이전에는 유료 이메일을 사이드바에 입력하기만 하면(소유권 검증 없이) 열람이 풀렸다 —
누군가의 결제 이메일 주소를 알기만 해도 접근할 수 있는 구조였다. send_login_otp/verify_login_otp
는 6자리 코드를 이메일로 보내 실제 소유자인지 확인한다. 별도 DB 없이 동작하도록, 코드/만료
시각은 이 모듈이 아니라 호출부(app.py)의 st.session_state 에 보관한다 — 발급과 검증이 항상
같은 브라우저 세션 안에서 끝나므로 서명된 토큰이나 서버 측 저장소가 필요 없다.
"""
import json
import random
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import brevo
import config

OTP_TTL_MINUTES = 10


def is_paid_email(email: str) -> bool:
    """Brevo 유료 리스트에 해당 이메일이 있으면 True. 미설정/조회 실패 시 False(안전한 기본값)."""
    email = (email or "").strip().lower()
    if not email:
        return False
    key = config.brevo_api_key()
    list_id = config.brevo_paid_list_id()
    if not key or not list_id:
        return False

    url = f"https://api.brevo.com/v3/contacts/{urllib.parse.quote(email, safe='')}"
    req = urllib.request.Request(url, headers={"Accept": "application/json", "api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError:
        return False  # 404(연락처 없음) 포함 — 조회 실패는 모두 미유료로 안전하게 처리
    except Exception:
        return False
    return int(list_id) in (data.get("listIds") or [])


def send_login_otp(email: str) -> tuple:
    """유료 이메일 확인 후 6자리 로그인 코드 발송.
    (True, otp_state) 또는 (False, 에러코드: invalid_email|not_paid|not_configured|error).
    otp_state 는 호출부가 st.session_state 에 보관했다가 verify_login_otp 에 그대로 넘긴다."""
    email = (email or "").strip().lower()
    if not email:
        return False, "invalid_email"
    if not is_paid_email(email):
        return False, "not_paid"

    key = config.brevo_api_key()
    admin_email, sender_name = config.brevo_sender()
    if not key or not admin_email:
        return False, "not_configured"

    code = f"{random.randint(0, 999999):06d}"
    ok = brevo.send_transactional_email(
        admin_email, sender_name, email,
        "[Dhandho Screener] 로그인 인증 코드",
        f"<p>아래 6자리 코드를 대시보드 사이드바에 입력하세요 ({OTP_TTL_MINUTES}분간 유효):</p>"
        f"<p style='font-size:28px;font-weight:bold;letter-spacing:4px'>{code}</p>",
        key,
    )
    if not ok:
        return False, "error"

    expires = (datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)).isoformat()
    return True, {"email": email, "code": code, "expires": expires}


def verify_login_otp(otp_state: dict, email: str, code: str) -> bool:
    """otp_state(send_login_otp 반환값)와 사용자 입력을 대조. 이메일 불일치·코드 불일치·만료 시 False."""
    if not otp_state:
        return False
    email = (email or "").strip().lower()
    code = (code or "").strip()
    if not code or email != otp_state.get("email") or code != otp_state.get("code"):
        return False
    try:
        expires = datetime.fromisoformat(otp_state["expires"])
    except Exception:
        return False
    return datetime.now(timezone.utc) < expires
