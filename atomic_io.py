# -*- coding: utf-8 -*-
"""프로세스 안에서와 프로세스 사이에서 안전한 텍스트 파일 쓰기.

임시 파일에 쓴 뒤 os.replace 로 바꾼다. 같은 경로의 잠금 파일에 fcntl 배타 잠금을 건다.
임시 파일 이름은 PID 만 쓰면 같은 프로세스의 스레드가 한 경로를 공유한다. 잠금을 푼 뒤에
그 파일을 지우면, 다음 스레드가 같은 이름을 만든 직후 지워져 os.replace 가
FileNotFoundError 가 된다. 이름은 스레드마다 다르게 하고, 삭제는 잠금을 풀기 전에 한다.
"""
import fcntl
import os
import threading
from pathlib import Path


def atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    with open(lock_path, "a+", encoding="utf-8") as lockf:
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
        try:
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, path)
        finally:
            try:
                tmp.unlink(missing_ok=True)
            finally:
                fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)
