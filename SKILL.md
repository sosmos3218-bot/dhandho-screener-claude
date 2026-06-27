---
name: dhandho-weekly-snapshot
description: 매주 월요일 오전 8시 Dhandho 스크리닝 스냅샷 자동 생성 및 신규/탈락 종목 추적
---

매주 월요일 오전 8시에 Dhandho 가치투자 스크리닝 주간 스냅샷을 생성한다.
**로컬 launchd 에이전트**(`com.user.dhandho-snapshot`)가 `snapshot_cron.sh` 를 실행한다.

## 목표
넓은 유니버스(미국 S&P 500 전체 + 한국 워치리스트)를 스캔해 Dhandho 4축 조건을
통과하는 종목을 발굴하고, 직전 주 대비 신규 진입/탈락 종목을 기록한다.

## 자동 실행 (이미 설치됨)
- 에이전트: `~/Library/LaunchAgents/com.user.dhandho-snapshot.plist` (매주 월 08:00)
- 실행: `.venv/bin/python3 snapshot.py ALL` 직접 (bash 래퍼 미경유 — TCC 책임 프로세스를 파이썬으로)
- 산출물:
  - `snapshots/dhandho_YYYY-MM-DD.json` : 통과 종목 스냅샷
  - `snapshots/diff_YYYY-MM-DD.md` : 직전 대비 신규/탈락 + 현재 통과 리스트
  - `logs/launchd.{out,err}.log` : 실행 로그
- **1회 수동 설정(완료됨)**: 전체 디스크 접근 권한에 Python 프레임워크
  (`/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14`) 허용.
  (`~/Documents` 보호 폴더 접근용. 미설정 시 exit 126 — `launchd.err.log` 의 "Operation not permitted")

## 수동 실행 / 즉시 실행
```bash
cd /Users/yhso/Documents/Claude/dhandho-screener
./snapshot_cron.sh                                              # 래퍼로 실행(로그 포함)
# 또는
launchctl kickstart gui/$(id -u)/com.user.dhandho-snapshot     # 예약 잡 즉시 1회
```

## (선택) 리포트 작성
`diff_YYYY-MM-DD.md` 를 읽어 다음을 요약하면 좋다:
- **🆕 신규 진입**: 종목별 한 줄 코멘트 — 왜 지금 매력적인가 (강한 FCF? 저부채? 저평가 진입?)
- **❌ 탈락**: 추정 사유 (가격 상승으로 저평가 해소? 부채 증가?)
- **총평**: 통과 종목 수 추세로 시장 전반의 고/저평가 진단, 주목 후보 1~2개

## 핵심 원칙 (Dhandho)
- "Heads I win, tails I don't lose much" — 하방 방어(낮은 부채·강한 현금흐름) 최우선
- 강한 FCF 를 헐값에(낮은 P/FCF) · 독점적 해자(ROIC·마진 안정성 + 정성 태그) · 깊은 안전마진(낮은 P/E·P/B, 높은 EBIT/EV)
- 금융주(은행/보험)는 본 모델로 과소평가되는 것이 정상
- 해자·KOSDAQ 폴백값은 정성/수동 → 투자 판단 전 DART·FnGuide 검증 권고
- 본 리포트는 정보 제공용, 투자 권유 아님

## 누적 보관
`snapshots/` 의 JSON/diff 는 삭제하지 않고 누적 (신규/탈락 시계열 추적용).
