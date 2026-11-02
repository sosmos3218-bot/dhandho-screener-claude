# -*- coding: utf-8 -*-
"""프로세스 사이에서 안전한 텍스트 파일 쓰기.

임시 파일에 쓴 뒤 os.replace 로 바꾼다. 같은 경로의 잠금 파일에 fcntl 배타 잠금을 건다.
"""
import fcntl
import os
from pathlib import Path


def atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with open(lock_path, "a+", encoding="utf-8") as lockf:
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
        try:
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, path)
        finally:
            fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)
            tmp.unlink(missing_ok=True)
