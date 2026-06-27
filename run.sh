#!/usr/bin/env bash
# 단도(Dhandho) 가치투자 스크리닝 대시보드 실행
cd "$(dirname "$0")"
exec .venv/bin/streamlit run app.py "$@"
