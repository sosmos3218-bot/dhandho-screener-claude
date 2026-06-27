# -*- coding: utf-8 -*-
"""
주간 통합 러너 (launchd 가 매주 월 08:00 실행)
==============================================
1) 전체 유니버스 스캔 → 스냅샷 + diff 저장        (snapshot.py)
2) 최신 스냅샷 → 뉴스레터 HTML+MD 생성            (newsletter.py)
3) secrets.json 이 있으면 SMTP 발송 (opt-in)

launchd 는 bash 래퍼 없이 이 파일을 venv 파이썬으로 직접 실행한다
(macOS TCC: 책임 프로세스를 파이썬으로 만들기 위함).
"""
import datetime as dt
import sys
import traceback

import newsletter
import snapshot


def main():
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n===== [{ts}] Dhandho 주간 파이프라인 시작 =====", flush=True)

    # 1) 스냅샷 (전체 유니버스)
    try:
        snapshot.run("ALL")
    except Exception:
        print("❌ 스냅샷 단계 실패:", flush=True)
        traceback.print_exc()
        return 1

    # 2) 뉴스레터 생성
    payload = newsletter.generate()
    if payload is None:
        print("❌ 뉴스레터 생성 실패 (스냅샷 없음)", flush=True)
        return 1

    # 3) 발송 (secrets.json 있을 때만 / --no-send 로 끌 수 있음)
    if "--no-send" not in sys.argv:
        try:
            newsletter.send(payload)
        except Exception:
            print("⚠️ 발송 단계 예외 (생성물은 정상 저장됨):", flush=True)
            traceback.print_exc()

    print(f"===== [{ts}] 완료 =====", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
