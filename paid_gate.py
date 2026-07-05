# -*- coding: utf-8 -*-
"""
유료 구독 상태 확인
====================
결제 자체는 Stripe Payment Link 가 처리하고, 결제 완료 웹훅(webhook/)이 구매자 이메일을
Brevo 유료 리스트(BREVO_PAID_LIST_ID)에 자동으로 추가한다. 이 모듈은 그 리스트에
이메일이 있는지 조회만 한다 — 결제 로직은 이 저장소가 아니라 Cloudflare Worker(webhook/)에 있다.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

import config


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
