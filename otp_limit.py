# -*- coding: utf-8 -*-
"""로그인 코드 발송의 서버 측 속도 제한.

세션이 아니라 디스크에 남긴다. 같은 프로세스의 새 세션에서도 적용된다.
단일 인스턴스(HF Space, 로컬) 기준이다. 인스턴스가 여러 대면 저장소를 공유해야 한다.
"""
import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

COOLDOWN_SEC = 60
MAX_PER_HOUR = 5

_LOCK = threading.Lock()
_DEFAULT_PATH = Path(__file__).resolve().parent / ".cache" / "otp_rate.json"


def _now(now):
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now


def _load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, path)


def check_and_mark(email: str, *, now=None, path: Path = None,
                   cooldown_sec: int = COOLDOWN_SEC, max_per_hour: int = MAX_PER_HOUR) -> bool:
    """보내도 되면 True 를 반환하고 시각을 기록한다. 제한에 걸리면 False."""
    email = (email or "").strip().lower()
    if not email:
        return False
    moment = _now(now)
    path = Path(path) if path is not None else _DEFAULT_PATH
    horizon = moment - timedelta(hours=1)
    with _LOCK:
        data = _load(path)
        stamps = []
        for raw in data.get(email) or []:
            try:
                ts = datetime.fromisoformat(raw)
            except Exception:
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= horizon:
                stamps.append(ts)
        if stamps and (moment - max(stamps)).total_seconds() < cooldown_sec:
            data[email] = [ts.isoformat() for ts in stamps]
            _save(path, data)
            return False
        if len(stamps) >= max_per_hour:
            data[email] = [ts.isoformat() for ts in stamps]
            _save(path, data)
            return False
        stamps.append(moment)
        data[email] = [ts.isoformat() for ts in stamps]
        _save(path, data)
        return True
