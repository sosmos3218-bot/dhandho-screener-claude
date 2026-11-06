#!/usr/bin/env python3
"""Brevo 커스텀 컨택 속성(attribute) 스키마를 보장한다.

Brevo는 스키마에 등록되지 않은 커스텀 속성을 컨택에 보내면 에러 없이 "조용히 무시"한다.
이 프로젝트가 컨택에 실어보내는 REQUESTED_TICKER / JOINED_AT / EARLYBIRD / PROCESSED / VALIDATION
/ SOURCE / UTM_SOURCE / UTM_MEDIUM / UTM_CAMPAIGN / UTM_CONTENT / UTM_TERM
등은 사전에 이 스크립트로 스키마를 만들어둬야 실제로 저장된다 (한 번만 실행하면 됨, 멱등).

Usage: ensure_brevo_attributes.py
"""
import json
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import attribution  # noqa: E402
import brevo  # noqa: E402
import privacy  # noqa: E402

SECRETS_PATH = Path(__file__).resolve().parent.parent / "secrets.json"

ATTRIBUTES = {
    "JOINED_AT": "text",
    "EARLYBIRD": "boolean",
    "REQUESTED_TICKER": "text",
    "PROCESSED": "boolean",
    "VALIDATION": "text",
    # 가입 채널. 무료/대기 가입은 utm_source 또는 direct.
    # 결제 웹훅/관리자 수동 추가는 각자 다른 문구를 넣는다.
    "SOURCE": "text",
    "EXPIRES_AT": "text",   # 관리자 한시적 접근 부여용 만료일(YYYY-MM-DD). paid_gate.is_expired
}
ATTRIBUTES.update({name: "text" for name in attribution.BREVO_UTM_ATTRIBUTES.values()})
ATTRIBUTES.update(privacy.BREVO_CONSENT_ATTRIBUTES)


def main() -> int:
    try:
        secrets = json.loads(SECRETS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(json.dumps({"error": f"Failed to read secrets.json: {e}"}))
        return 1

    api_key = (secrets.get("brevo_api_key") or "").strip()
    if not api_key:
        print(json.dumps({"error": "brevo_api_key missing in secrets.json"}))
        return 1

    existing = brevo.list_attribute_names(api_key)

    results = {}
    for name, attr_type in ATTRIBUTES.items():
        if name in existing:
            results[name] = "already exists"
            continue
        try:
            brevo.create_attribute(name, attr_type, api_key)
            results[name] = "created"
        except urllib.error.HTTPError as e:
            results[name] = f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')}"
        except Exception as e:
            results[name] = f"error: {e}"

    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
