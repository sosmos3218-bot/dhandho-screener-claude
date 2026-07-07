#!/usr/bin/env python3
"""관리자용: 유료 구독자를 Brevo 유료 리스트(brevo_paid_list_id)에 직접 추가/제거/조회한다.

결제 자동화(Stripe/Polar → webhook/)를 아직 붙이기 전, 관리자가 직권으로 유료 구독자를
등록하거나 현재 명단을 확인할 때 쓴다. 자동화를 붙인 뒤에도 수동 보정용으로 계속 쓸 수 있다.

Usage:
  .venv/bin/python scripts/manage_paid_subscribers.py list
  .venv/bin/python scripts/manage_paid_subscribers.py add <email> [email2 ...]
  .venv/bin/python scripts/manage_paid_subscribers.py remove <email> [email2 ...]
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import brevo  # noqa: E402
import config  # noqa: E402
import waitlist  # noqa: E402


def _key_and_list():
    key = config.brevo_api_key()
    list_id = config.brevo_paid_list_id()
    if not key or not list_id:
        print("brevo_api_key / brevo_paid_list_id 미설정")
        return None, None
    return key, list_id


def cmd_list() -> int:
    key, list_id = _key_and_list()
    if not key:
        return 1
    contacts = brevo.list_contacts_in_list(list_id, key)
    if not contacts:
        print("유료 구독자 없음.")
        return 0
    print(f"유료 구독자 {len(contacts)}명:")
    for c in sorted(contacts, key=lambda c: c.get("email") or ""):
        attrs = c.get("attributes") or {}
        joined = attrs.get("JOINED_AT", "")
        source = attrs.get("SOURCE", "")
        extra = " · ".join(x for x in [source, joined] if x)
        print(f"  - {c.get('email')}" + (f"  ({extra})" if extra else ""))
    return 0


def cmd_add(emails: list) -> int:
    key, list_id = _key_and_list()
    if not key:
        return 1
    ok_count = 0
    for raw in emails:
        email = raw.strip().lower()
        if not waitlist.is_valid_email(email):
            print(f"  ⚠️  {raw} — 이메일 형식이 아니라 건너뜀")
            continue
        ok = brevo.add_contact_to_list(email, list_id, {
            "SOURCE": "admin manual add",
            "JOINED_AT": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }, key)
        print(f"  {'✅' if ok else '❌'} {email}")
        ok_count += 1 if ok else 0
    print(f"{ok_count}/{len(emails)}명 추가 완료.")
    return 0 if ok_count == len(emails) else 1


def cmd_remove(emails: list) -> int:
    key, list_id = _key_and_list()
    if not key:
        return 1
    emails = [e.strip().lower() for e in emails]
    result = brevo.remove_contacts_from_list(list_id, emails, key)
    outcome = result.get("contacts", result)
    for email in outcome.get("success", []):
        print(f"  ✅ {email}")
    for email in outcome.get("failure", []):
        print(f"  ❌ {email}")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "list":
        return cmd_list()
    if cmd == "add":
        if not args:
            print("이메일을 하나 이상 지정하세요.")
            return 1
        return cmd_add(args)
    if cmd == "remove":
        if not args:
            print("이메일을 하나 이상 지정하세요.")
            return 1
        return cmd_remove(args)
    print(f"알 수 없는 명령: {cmd}\n")
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
