#!/usr/bin/env python3
"""관리자용 CLI: 유료 구독자를 Brevo 유료 리스트(brevo_paid_list_id)에 직접 추가/제거/조회한다.

같은 기능을 로컬 실행 없이 쓰려면 배포된 대시보드 URL에 ?admin=1 을 붙인 관리자 페이지
(admin_page.py)를 쓰면 된다 — 둘 다 paid_gate.list_paid_subscribers/add_paid_subscriber/
remove_paid_subscribers 를 그대로 호출하므로 결과가 어긋나지 않는다. 이 스크립트는 스크립팅/
일괄 등록처럼 로컬 CLI가 더 편한 경우를 위한 보조 경로로 남겨둔다.

Usage:
  .venv/bin/python scripts/manage_paid_subscribers.py list
  .venv/bin/python scripts/manage_paid_subscribers.py add <email> [email2 ...]
  .venv/bin/python scripts/manage_paid_subscribers.py remove <email> [email2 ...]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import paid_gate  # noqa: E402
import waitlist  # noqa: E402


def _check_configured() -> bool:
    if not config.brevo_api_key() or not config.brevo_paid_list_id():
        print("brevo_api_key / brevo_paid_list_id 미설정")
        return False
    return True


def cmd_list() -> int:
    if not _check_configured():
        return 1
    contacts = paid_gate.list_paid_subscribers()
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
    if not _check_configured():
        return 1
    ok_count = 0
    for raw in emails:
        email = raw.strip().lower()
        if not waitlist.is_valid_email(email):
            print(f"  ⚠️  {raw} — 이메일 형식이 아니라 건너뜀")
            continue
        ok = paid_gate.add_paid_subscriber(email)
        print(f"  {'✅' if ok else '❌'} {email}")
        ok_count += 1 if ok else 0
    print(f"{ok_count}/{len(emails)}명 추가 완료.")
    return 0 if ok_count == len(emails) else 1


def cmd_remove(emails: list) -> int:
    if not _check_configured():
        return 1
    result = paid_gate.remove_paid_subscribers(emails)
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
