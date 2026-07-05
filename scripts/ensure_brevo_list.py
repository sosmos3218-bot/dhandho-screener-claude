#!/usr/bin/env python3
"""Ensure a named Brevo list exists; print list_id and status (created|reused).

Usage: ensure_brevo_list.py <list name> <secrets.json key to write the id into>
Example: ensure_brevo_list.py "Dhandho Screener - Free" brevo_free_list_id
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

SECRETS_PATH = Path(__file__).resolve().parent.parent / "secrets.json"


def main() -> int:
    if len(sys.argv) != 3:
        print(json.dumps({"error": "usage: ensure_brevo_list.py <list name> <secrets key>"}))
        return 1
    list_name, secrets_key = sys.argv[1], sys.argv[2]

    try:
        secrets = json.loads(SECRETS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(json.dumps({"error": f"Failed to read secrets.json: {e}"}))
        return 1

    api_key = (secrets.get("brevo_api_key") or "").strip()
    if not api_key:
        print(json.dumps({"error": "brevo_api_key missing in secrets.json"}))
        return 1

    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # GET existing lists
    req = urllib.request.Request(
        "https://api.brevo.com/v3/contacts/lists?limit=50",
        headers=headers,
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(json.dumps({"error": f"GET lists failed: HTTP {e.code}", "body": body}))
        return 1
    except Exception as e:
        print(json.dumps({"error": f"GET lists failed: {e}"}))
        return 1

    def _finish(list_id: str, status: str) -> int:
        secrets[secrets_key] = list_id
        SECRETS_PATH.write_text(json.dumps(secrets, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"list_id": list_id, "status": status, "error": None, "secrets_updated": True}))
        return 0

    for lst in data.get("lists") or []:
        if (lst.get("name") or "").strip() == list_name:
            return _finish(str(lst["id"]), "reused")

    # POST new list
    payload = json.dumps({"name": list_name, "folderId": 1}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.brevo.com/v3/contacts/lists",
        data=payload,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            created = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(json.dumps({"error": f"POST list failed: HTTP {e.code}", "body": body}))
        return 1
    except Exception as e:
        print(json.dumps({"error": f"POST list failed: {e}"}))
        return 1

    list_id = str(created.get("id", ""))
    if not list_id:
        print(json.dumps({"error": "POST succeeded but no id in response", "response": created}))
        return 1

    return _finish(list_id, "created")


if __name__ == "__main__":
    sys.exit(main())
