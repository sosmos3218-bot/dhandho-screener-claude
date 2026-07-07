# -*- coding: utf-8 -*-
"""Brevo REST API 공용 헬퍼.

waitlist.py / scripts/ensure_brevo_list.py / scripts/ensure_brevo_attributes.py /
scripts/process_universe_requests.py 가 각자 흉내내던 urllib 기반 Brevo 호출
보일러플레이트(헤더 구성, JSON 인코드/디코드)를 한 곳에 모은다.

`request()`는 실패 시 urllib.error.HTTPError/기타 예외를 그대로 올린다 — 호출부가
"에러를 보여줘야 하는 관리자 스크립트"인지 "실패해도 조용히 넘어가는 best-effort"인지에
따라 처리 방식이 다르므로, 이 모듈은 그 결정을 내리지 않는다.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

_BASE = "https://api.brevo.com/v3"


def _headers(key: str) -> dict:
    return {"api-key": key, "Content-Type": "application/json", "Accept": "application/json"}


def request(method: str, path: str, key: str, payload: dict = None, timeout: int = 15) -> dict:
    """Brevo API 호출. 성공 시 응답 바디를 dict로 파싱해 반환(바디 없으면 {})."""
    url = path if path.startswith("http") else f"{_BASE}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=_headers(key), method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
        return json.loads(body.decode("utf-8")) if body else {}


def add_contact_to_list(email: str, list_id: str, attributes: dict, key: str) -> bool:
    """컨택을 리스트에 추가(이미 있으면 속성 갱신). 성공 시 True."""
    payload = {"email": email, "listIds": [int(list_id)], "updateEnabled": True, "attributes": attributes}
    try:
        request("POST", "/contacts", key, payload)
        return True
    except urllib.error.HTTPError as e:
        return e.code == 204  # 이미 등록된 이메일(업데이트)도 정상 처리
    except Exception:
        return False


def update_contact(email: str, attributes: dict, key: str) -> bool:
    """기존 컨택의 속성만 갱신. 실패해도 예외를 올리지 않고 False만 반환(best-effort)."""
    try:
        request("PUT", f"/contacts/{urllib.parse.quote(email)}", key, {"attributes": attributes})
        return True
    except Exception:
        return False


def send_transactional_email(sender_email: str, sender_name: str, to_email: str,
                              subject: str, html: str, key: str) -> bool:
    """트랜잭션 메일 발송. 실패해도 예외를 올리지 않고 False만 반환(best-effort)."""
    payload = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html,
    }
    try:
        request("POST", "/smtp/email", key, payload)
        return True
    except Exception:
        return False


def list_contacts_in_list(list_id: str, key: str, limit: int = 50) -> list:
    """리스트에 속한 모든 컨택(raw dict, attributes 포함)을 페이지네이션하며 모두 가져온다."""
    out, offset = [], 0
    while True:
        page = request("GET", f"/contacts/lists/{list_id}/contacts?limit={limit}&offset={offset}", key)
        contacts = page.get("contacts", [])
        if not contacts:
            break
        out.extend(contacts)
        offset += limit
        if offset >= page.get("count", 0):
            break
    return out


def list_lists(key: str, limit: int = 50) -> list:
    """전체 컨택 리스트(이름/id 등 raw dict) 조회."""
    return request("GET", f"/contacts/lists?limit={limit}", key).get("lists") or []


def create_list(name: str, key: str, folder_id: int = 1) -> dict:
    """새 컨택 리스트 생성. 응답 raw dict(id 포함)를 그대로 반환."""
    return request("POST", "/contacts/lists", key, {"name": name, "folderId": folder_id})


def list_attribute_names(key: str) -> set:
    """등록된 커스텀 컨택 속성(attribute) 이름 전체."""
    return {a["name"] for a in request("GET", "/contacts/attributes", key).get("attributes", [])}


def create_attribute(name: str, attr_type: str, key: str) -> None:
    """커스텀 컨택 속성 스키마 등록(예: type='text'|'boolean')."""
    request("POST", f"/contacts/attributes/normal/{name}", key, {"type": attr_type})
