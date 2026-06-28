# 🏰 Dhandho 가치투자 스크리너

모니시 파브라이의 『단도(Dhandho)』 투자 철학 —
**"Heads I win, tails I don't lose much"** — 을 정량 필터로 옮긴 개인용 스크리닝 대시보드.

> 강한 잉여현금흐름을, 낮은 부채와 독점적 해자를 가진 기업을, 깊은 안전마진(저평가)에 산다.

**대상 시장**: 🇺🇸 미국(S&P 500 전체) · 🇰🇷 한국(워치리스트) · 🇯🇵 일본(도쿄증시 대형·우량주, `.T`)
**주요 기능**: 스크리닝 대시보드 · 주간 스냅샷/뉴스레터 자동발행 · 🩺 포트폴리오 건강검진(보유종목 4축 객관 진단)

## Dhandho 4축 스크리닝 모델

| 축 | 지표 | 기본 임계값 | 데이터원 |
|----|------|-----------|---------|
| ① 시총 대비 현금흐름 | FCF Yield = FCF/시총, P/FCF | FCF Yield ≥ 8%, P/FCF ≤ 15 | 미국 자동 / 한국 수동 |
| ② 낮은 부채 | 부채/자본, 순부채/EBITDA | D/E ≤ 0.5, ND/EBITDA ≤ 2.5 | 미국 자동 / 한국 수동 |
| ③ 독점적 해자(Moat) | ROIC, 매출총이익률, 영업이익률 안정성 + 정성 태그 | ROIC ≥ 15%, GM ≥ 40% | ROIC/마진=자동, 태그=수동 |
| ④ 저평가/안전마진 | P/E, P/B, 이익수익률(EBIT/EV) | P/E ≤ 15, P/B ≤ 3, EY ≥ 8% | 미국 자동 / 한국 수동 |

- **Dhandho Score(0~100)** = 4축 정규화 점수의 가중합 (현금흐름 35% · 부채 20% · 해자 25% · 저평가 20%).
- **통과 규칙**: 4개 축 중 3개 이상 충족 + **부채 축 필수**(하방 방어 우선).
- **하방방어 게이지**: 부채·현금흐름 기반 "tails I don't lose much" 점수 별도 표기.

## 데이터 출처

- 🟢 **LIVE (대부분 자동)**
  - 미국: `yfinance` — 시가총액·FCF·부채·ROIC·마진·순이익·P/E·P/B 자동 수집 (S&P 500 전체)
  - 한국: `yfinance` `.KS`(KOSPI)/`.KQ`(KOSDAQ) — 펀더멘털 자동 수집 + `pykrx` 로 LIVE 가격
    - PE/PB 는 시총÷순이익, 시총÷자본 으로 직접 계산 (KRX 는 yfinance 가 비율을 안 주는 경우가 많음)
    - KOSDAQ 은 yfinance 결측이 잦아 `config.py` 의 폴백 수동값(shares/eps/bvps) 사용
  - 일본: `yfinance` `.T`(도쿄증시) — 가격·펀더멘털 모두 자동 (JPY). 버핏 5대 상사·일본담배(JT) 등 포함
- 🟡 **INPUT (수동, `config.py`)**
  - 해자(Moat) 정성 태그 (wide / narrow / none) — 사람이 판단
  - yfinance 결측 시 폴백 수동값 (선택)
  - ⚠️ 은행/보험 등 금융주는 FCF·부채 구조가 달라 본 모델로 과소평가될 수 있음 (점수 낮게 나오는 것이 정상)

## 설치 & 실행

```bash
cd dhandho-screener
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 대시보드
./run.sh                       # = .venv/bin/streamlit run app.py

# 주간 스냅샷(통과 종목 + 신규/탈락 diff)
.venv/bin/python snapshot.py ALL
```

## 파일 구성

| 파일 | 역할 |
|------|------|
| `config.py` | 임계값·가중치·미국 유니버스·한국 워치리스트(수동 INPUT)·해자 태그 |
| `data.py` | LIVE 수집 (yfinance / pykrx) + 디스크 캐시 |
| `screening.py` | Dhandho 지표·점수·플래그 계산, `build_universe()` |
| `app.py` | Streamlit 대시보드 (필터·KPI·테이블·차트·레이더·스냅샷 diff) |
| `snapshot.py` | 주간 스냅샷 + 신규/탈락 diff 생성 |
| `newsletter.py` | 스냅샷 → 뉴스레터 HTML+MD 생성 + opt-in SMTP 발송 |
| `weekly_run.py` | **launchd 진입점** — 스냅샷 + 뉴스레터(+발송) 통합 실행 |
| `secrets.example.json` | SMTP/구독자 설정 템플릿 (`secrets.json` 으로 복사해 사용) |
| `snapshot_cron.sh` | 수동 실행용 bash 래퍼(로그 포함) |
| `SKILL.md` | 주간 스케줄 자동 리포트 정의 |
| `snapshots/` · `newsletter/` | 스냅샷·뉴스레터 산출물 누적 |
| `~/Library/LaunchAgents/com.user.dhandho-snapshot.plist` | 주간 실행 launchd 에이전트 |

## 자동 업데이트

- **접속 시 라이브**: Streamlit `@st.cache_data`(TTL 12h) + 디스크 캐시로 최신화. 사이드바 "새로고침"으로 강제 갱신.
- **주간 파이프라인 (launchd, 매주 월 08:00)**: venv 파이썬이 `weekly_run.py` 를 실행 →
  ① 전체 유니버스(S&P500 + 한국) 재스캔 → 스냅샷·diff 저장,
  ② 뉴스레터 HTML+MD 생성(`newsletter/`),
  ③ `secrets.json` 이 있으면 구독자에게 SMTP 발송.
  - 설치된 에이전트: `~/Library/LaunchAgents/com.user.dhandho-snapshot.plist`
    (bash 래퍼를 거치지 않고 `.venv/bin/python3 weekly_run.py` 직접 실행 — TCC 책임 프로세스를 파이썬으로 만들기 위함)
  - 등록/해제/즉시실행:
    ```bash
    launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.user.dhandho-snapshot.plist   # 등록
    launchctl bootout   gui/$(id -u)/com.user.dhandho-snapshot                                 # 해제
    launchctl kickstart -k gui/$(id -u)/com.user.dhandho-snapshot                              # 지금 즉시 1회 실행
    ```
  - ⚠️ **1회 수동 설정(macOS TCC)**: `~/Documents` 는 보호 폴더라 백그라운드 에이전트의 접근이 기본 차단됨.
    **시스템 설정 → 개인정보 보호 및 보안 → 전체 디스크 접근 권한**에서 **Python**
    (`/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14`)을 추가·허용해야 예약 실행이 동작한다. ✅ *설정 완료됨.*
    (`./snapshot_cron.sh` 수동 실행은 권한과 무관하게 동작.)
  - 실행 로그: `logs/launchd.{out,err}.log` (수동 래퍼는 `logs/cron.log`)

## 📧 주간 뉴스레터

스냅샷을 읽기 좋은 뉴스레터로 자동 발행한다. **규제 안전을 위해 "매수 추천"이 아니라
정량 기준 통과 목록 + 교육적 해설** 형식이며, 모든 발행물에 비투자권유 면책을 포함한다.

```bash
.venv/bin/python newsletter.py          # 생성만 → newsletter/dhandho_YYYY-MM-DD.{html,md}
.venv/bin/python newsletter.py --send   # 생성 + SMTP 발송 (secrets.json 필요)
```

- **파일 생성(기본)**: `newsletter/` 에 HTML(이메일/플랫폼용, 인라인 스타일)과 마크다운(스티비/Substack 붙여넣기용) 동시 생성.
- **이메일 발송(opt-in)**: `secrets.example.json` → `secrets.json` 으로 복사 후 SMTP 정보·구독자 입력 시 활성화.
  - Gmail: 2단계 인증 후 **앱 비밀번호**([myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)) 발급해 넣기. 네이버는 메일 환경설정에서 SMTP 사용 설정.
  - `secrets.json` 은 `.gitignore` 로 제외됨 (절대 커밋 금지).
- 내용: 시장 온도(통과 비율 기반 코멘트) · 신규 진입/탈락 · 통과 Top 15 표 · 주차별 로테이션 교육 코너 · 면책.

## 🩺 포트폴리오 건강검진 (대시보드 탭)

보유종목을 입력하면 **Dhandho 4축 객관 점수**를 카드로 보여준다. 티커는 시장 자동 감지:
미국=`AAPL` · 한국=`005930`(6자리) · 일본=`7203.T`(.T). (data.fetch_auto)

**입력 방법** (`portfolio_io.py`):
- **엑셀/CSV 템플릿 다운로드** → 보유종목 채워서 **파일 업로드**(.xlsx/.csv) — `티커` 열 필수, `보유수량`·`평균단가`는 선택
- 또는 티커를 직접 입력(줄바꿈/콤마)
- 보유수량·평균단가가 있으면 각 카드에 **보유주수·평가손익%**를 사실 정보로 표시(동일통화 가정)

> ⚠️ **이 기능은 매수·매도·보유를 권유하지 않는다.** "물타기/손절" 판단을 대신하지 않으며,
> 각 종목이 4축에서 몇 점인지 + 상대적 강점/약점을 *사실로만* 제시한다. 해석·판단은 사용자 몫.
> (개인 맞춤 매매조언은 투자자문업 인가 영역이므로 의도적으로 배제 — 정보·교육 범위 유지.)

## 한계 / 주의

- `yfinance` 는 비공식 스크레이퍼 → 다수 티커 스캔 시 레이트리밋·결측 가능. 디스크 캐시·지연·graceful skip 으로 방어하되, 처음엔 미국 스캔 종목 수를 20개로 두고 검증 후 확대 권장.
- **해자(Moat)는 본질적으로 정성 판단**. ROIC·마진 안정성·수동 태그는 근사 보조 지표일 뿐 — 실제 사업 분석을 대체하지 않는다.
- 한국 펀더멘털은 PLACEHOLDER 초기값. 반드시 검증·갱신.
- ⚠️ 본 도구는 정보 제공용이며 **투자 권유가 아니다.**
