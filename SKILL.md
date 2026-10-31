---
name: dhandho-weekly-snapshot
description: 매주 월요일 오전 8시(KST) Dhandho 스크리닝을 GitHub Actions에서 실행한다
---

매주 월요일 08:00 KST에 Dhandho 스크리닝 주간 스냅샷을 만든다.
실행 경로는 GitHub Actions `.github/workflows/weekly.yml` 이다.
로컬 launchd는 주 경로가 아니다.

## 목표
미국 S&P 500, 한국 워치리스트, 일본 종목을 스캔해 사전에 정한 4개 축을
통과한 종목을 기록하고, 직전 주와 비교해 들어온 종목과 빠진 종목을 남긴다.

## 자동 실행
- 워크플로: `.github/workflows/weekly.yml`
- 예약: 일요일 23:00 UTC, 월요일 08:00 KST
- 산출물:
  - `snapshots/dhandho_YYYY-MM-DD.json`
  - `snapshots/diff_YYYY-MM-DD.md`
  - `published/screening_data.json` (`skip` 에 시장별 시도, 스킵 수)
- 시장별 스킵 비율이 `SKIP_RATE_THRESHOLD`(기본 0.10)를 넘거나 퍼블리시 또는 발송이 실패하면
  그 실행의 산출물은 main에 커밋하지 않는다.

## 수동 실행
```bash
python weekly_run.py --no-send
```

## 리포트 작성
`diff_YYYY-MM-DD.md` 를 읽을 때 매수를 권하는 문장을 쓰지 않는다.
- 신규 진입: 어떤 축(현금흐름, 부채, ROIC, P/E)을 통과했는지
- 탈락: 어떤 축이 기준 밖으로 나갔는지
- 총평: 통과 종목 수와 비율
- 한 줄 면책: 사전에 정한 조건을 통과한 목록이며 투자 권유가 아닙니다.

## 핵심 원칙
- "Heads I win, tails I don't lose much": 낮은 부채와 현금흐름을 먼저 본다
- 강한 FCF(낮은 P/FCF), ROIC와 마진, 낮은 P/E와 P/B, 높은 EBIT/EV
- 해자 태그 wide는 점수 보너스만 주고, 통과 조건을 대신하지 않는다
- 금융주(은행, 보험)는 이 모델에서 점수가 낮게 나오는 것이 흔하다
- 해자와 KOSDAQ 폴백값은 사람이 확인한다. 판단 전 DART, FnGuide를 본다
- 결과물은 정보 제공용이며 투자 권유가 아니다

## 누적 보관
`snapshots/` 의 JSON과 diff는 지우지 않고 쌓아 둔다.
