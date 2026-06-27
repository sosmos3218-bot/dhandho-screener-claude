#!/usr/bin/env bash
# 주간 Dhandho 스냅샷 실행 래퍼 (launchd LaunchAgent 가 호출)
# 전체 유니버스(S&P500 + 한국 워치리스트)를 스캔해 통과 종목 스냅샷 + diff 생성.
cd "$(dirname "$0")" || exit 1
mkdir -p logs
TS="$(date '+%Y-%m-%d %H:%M:%S')"
echo "===== [$TS] Dhandho 주간 스냅샷 시작 =====" >> logs/cron.log
.venv/bin/python snapshot.py ALL >> logs/cron.log 2>&1
echo "===== [$TS] 종료 (exit $?) =====" >> logs/cron.log
