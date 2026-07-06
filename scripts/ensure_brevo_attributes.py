#!/usr/bin/env python3
"""Brevo 커스텀 컨택 속성(attribute) 스키마를 보장한다.

Brevo는 스키마에 등록되지 않은 커스텀 속성을 컨택에 보내면 에러 없이 "조용히 무시"한다.
이 프로젝트가 컨택에 실어보내는 REQUESTED_TICKER / JOINED_AT / EARLYBIRD / PROCESSED / VALIDATION
등은 사전에 이 스크립트로 스키마를 만들어둬야 실제로 저장된다 (한 번만 실행하면 됨, 멱등).

Usage: ensure_brevo_attributes.py
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

SECRETS_PATH = Path(__file__).resolve().parent.parent / "secrets.json"

ATTRIBUTES = {
    "JOINED_AT": "text",
    "EARLYBIRD": "boolean",
    "REQUESTED_TICKER": "text",
    "PROCESSED": "boolean",
    "VALIDATION": "text",
}


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

    headers = {"api-key": api_key, "Content-Type": "application/json", "Accept": "application/json"}

    # 기존 스키마 조회 (이미 있는 속성은 건너뜀)
    req = urllib.request.Request("https://api.brevo.com/v3/contacts/attributes", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        existing = {a["name"] for a in json.loads(resp.read().decode("utf-8")).get("attributes", [])}

    results = {}
    for name, attr_type in ATTRIBUTES.items():
        if name in existing:
            results[name] = "already exists"
            continue
        payload = json.dumps({"type": attr_type}).encode("utf-8")
        req = urllib.request.Request(
            f"https://api.brevo.com/v3/contacts/attributes/normal/{name}",
            data=payload, headers=headers, method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=15)
            results[name] = "created"
        except urllib.error.HTTPError as e:
            results[name] = f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')}"
        except Exception as e:
            results[name] = f"error: {e}"

    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
