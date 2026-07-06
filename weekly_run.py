# -*- coding: utf-8 -*-
"""
주간 통합 러너 (GitHub Actions `.github/workflows/weekly.yml` 이 매주 월 08:00 KST 실행)
=======================================================================================
1) 전체 유니버스(S&P500+한국+일본) 1회 스캔        (screening.build_universe)
2) 그 결과로 스냅샷+diff 저장                       (snapshot.run(df=df))
3) 배포용 데이터 내보내기 published/screening_data.json (publish.run(df=df))
4) 뉴스레터 HTML+MD 생성 (+secrets/Brevo 있으면 발송) (newsletter)
5) (선택) git add/commit/push — 환경변수 DHANDHO_AUTO_PUSH=1 일 때만
         → 클라우드(Streamlit) 대시보드가 주간 자동 갱신됨
         (GitHub Actions 에서는 이 변수 대신 workflow 자체가 커밋·push 를 담당)

스캔을 1회만 하고 스냅샷·배포가 공유하므로 yfinance 레이트리밋 부담이 줄어든다.
2026-07-06 이전에는 로컬 launchd(bash 래퍼 없이 venv 파이썬 직접 실행)로 돌렸으나,
GitHub Actions의 해외 IP에서도 pykrx/yfinance가 안 막힘을 실측 검증한 뒤 완전히 이전했다
(로컬에서 수동 실행/디버깅 목적으로는 여전히 그대로 사용 가능).
"""
import datetime as dt
import os
import subprocess
import sys
import traceback

import newsletter
import publish
import screening
import snapshot

BASE = os.path.dirname(os.path.abspath(__file__))


def _auto_push():
    """published/ · snapshots/ 변경분을 커밋·push (best-effort)."""
    try:
        subprocess.run(["git", "-C", BASE, "add", "published", "snapshots"], check=True)
        # 변경 없으면 커밋 생략
        if subprocess.run(["git", "-C", BASE, "diff", "--staged", "--quiet"]).returncode == 0:
            print("ℹ️ 변경 없음 — push 생략", flush=True)
            return
        msg = f"data: weekly publish {dt.date.today().isoformat()}"
        subprocess.run(["git", "-C", BASE, "commit", "-m", msg], check=True)
        # 원격 변경 먼저 합치고 push (데이터 파일이라 충돌 거의 없음)
        subprocess.run(["git", "-C", BASE, "pull", "--rebase", "--autostash"], check=False)
        subprocess.run(["git", "-C", BASE, "push"], check=True)
        print("📤 git push 완료 (클라우드 데이터 갱신)", flush=True)
    except Exception:
        print("⚠️ auto-push 실패(생성물은 정상 저장됨):", flush=True)
        traceback.print_exc()


def main():
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n===== [{ts}] Dhandho 주간 파이프라인 시작 =====", flush=True)

    # 1) 전체 유니버스 1회 스캔
    try:
        df = screening.build_universe("ALL", use_cache=False)
    except Exception:
        print("❌ 유니버스 스캔 실패:", flush=True)
        traceback.print_exc()
        return 1
    if df is None or df.empty:
        print("❌ 수집 데이터 없음 — 중단", flush=True)
        return 1
    print(f"✅ 스캔 완료: {len(df)}종목 · 통과 {int(df['passes'].sum())}", flush=True)

    # 2) 스냅샷 + diff
    try:
        snapshot.run("ALL", df=df)
    except Exception:
        print("⚠️ 스냅샷 단계 예외:", flush=True)
        traceback.print_exc()

    # 3) 배포용 데이터
    try:
        publish.run(df=df)
    except Exception:
        print("⚠️ 퍼블리시 단계 예외:", flush=True)
        traceback.print_exc()

    # 4) 뉴스레터 생성 (+발송)
    payload = newsletter.generate()
    if payload and "--no-send" not in sys.argv:
        try:
            newsletter.send(payload)
        except Exception:
            print("⚠️ 발송 단계 예외(생성물은 정상 저장됨):", flush=True)
            traceback.print_exc()

    # 5) 선택적 자동 push
    if os.environ.get("DHANDHO_AUTO_PUSH") == "1":
        _auto_push()

    print(f"===== [{ts}] 완료 =====", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
