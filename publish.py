# -*- coding: utf-8 -*-
"""
배포용 데이터 퍼블리시
=====================
로컬(한국 IP)에서 전체 유니버스를 스캔·분석한 결과를
`published/screening_data.json` 으로 내보낸다.

클라우드 대시보드(app.py, 환경변수 DHANDHO_MODE=published)는 이 파일만 읽어 렌더하므로
클라우드에서는 yfinance/pykrx 를 호출하지 않는다 → 레이트리밋·한국 차단·속도 문제 회피.

사용:
    python publish.py            # 신선하게 전체 스캔 후 내보내기
    python publish.py --cache    # 디스크 캐시 사용(빠름, 테스트용)
"""
import datetime as dt
import json
import os
import sys

import screening

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE, "published")
OUT_FILE = os.path.join(OUT_DIR, "screening_data.json")


def run(use_cache: bool = False, limit=None, df=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    if df is None:  # df 를 넘기면 재스캔 생략 (weekly_run 이 1회 스캔 공유)
        df = screening.build_universe("ALL", use_cache=use_cache, limit=limit)
    if df.empty:
        print("⚠️ 수집 데이터 없음 — 퍼블리시 중단")
        return None

    # 전체 컬럼을 numpy/NaN 안전하게 직렬화 (to_json: numpy→기본형, NaN→null, list 컬럼 OK).
    # build_row 출력에 원시필드(market_cap·fcf·ebit…)가 모두 들어있어 클라우드에서 재채점 가능.
    rows = json.loads(df.to_json(orient="records"))

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "universe": "ALL (S&P500 + 한국 + 일본)",
        "n": len(df),
        "n_pass": int(df["passes"].sum()),
        "rows": rows,
    }
    json.dump(payload, open(OUT_FILE, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"✅ 퍼블리시: {OUT_FILE}  ({len(df)}종목 · 통과 {payload['n_pass']} · {payload['generated_at']})")
    return payload


if __name__ == "__main__":
    run(use_cache=("--cache" in sys.argv))
