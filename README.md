---
title: Dhandho Screener
emoji: 🏰
colorFrom: green
colorTo: gray
sdk: streamlit
app_file: app.py
pinned: false
---

# 🏰 Dhandho 가치투자 스크리너

모니시 파브라이의 『단도(Dhandho)』 투자 철학 —
**"Heads I win, tails I don't lose much"** — 을 정량 필터로 옮긴 개인용 스크리닝 대시보드.

> 강한 잉여현금흐름을, 낮은 부채와 독점적 해자를 가진 기업을, 깊은 안전마진(저평가)에 산다.

**대상 시장**: 🇺🇸 미국(S&P 500 전체) · 🇰🇷 한국(워치리스트) · 🇯🇵 일본(도쿄증시 대형·우량주, `.T`)
**주요 기능**: 스크리닝 대시보드 · 주간 스냅샷/뉴스레터 자동발행(무료/유료판 분리) · 🩺 포트폴리오 건강검진(보유종목 4축 객관 진단)

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
- **Codex 보조점수(0~100, A~D 밴드)**: 자매 프로젝트 `dhandho-korea-weekly-codex`(kospi_bubble_dashboard) 방식의
  포인트 합산 스코어(Cash 0~30 + Debt 0~25 + Moat×0.25 + Valuation 0~20)를 별도 컬럼으로 병기.
  통과 판정에는 반영하지 않는 교차검증용 지표 — 서로 다른 Dhandho 프로젝트들의 스코어링 산식 차이를 한 화면에서 비교할 수 있다.

## 🔓 무료/유료 티어

- **대시보드**: 무료판은 통과 종목 중 `config.FREE_TIER_SKIP+1`~`FREE_TIER_SKIP+FREE_TIER_LIMIT`위
  (기본 6~10위, 상위 1~5위는 비공개)만 미리보기로 표시 — 최상위 후보를 가리는 것 자체가 유료 전환 유인이다.
  사이드바에서 **결제한 이메일로 6자리 로그인 코드**를 받아 입력하면(`paid_gate.send_login_otp`/
  `verify_login_otp`) 전체 종목 + CSV 다운로드가 열린다 — 예전처럼 이메일을 입력하기만 하면 열리는
  방식이 아니라 실제 소유자 확인을 거친다. `config.session_secret`(HMAC 서명키)이 설정돼 있으면
  브라우저 쿠키로 `paid_gate.SESSION_TTL_DAYS`(기본 14일)간 로그인이 유지된다(탭을 닫아도 재인증
  불필요, 구독 취소 시 다음 방문에서 자동 재확인돼 즉시 차단). 미설정 시엔 이 기능만 꺼지고
  로그인은 브라우저 세션 안에서만 유지된다.
  키 생성: `python3 -c "import secrets; print(secrets.token_hex(32))"` → `secrets.json`의
  `session_secret` 또는 `SESSION_SECRET` 환경변수(클라우드 배포용)에 등록. **한 번 정하면 바꾸지
  말 것** — 바꾸면 기존 로그인 쿠키가 전부 무효화된다.
- **유료 구독자 수동 관리**: 결제 자동화(아래 웹훅)를 붙이기 전에는 관리자가 직접 Brevo 유료
  리스트에 이메일을 등록/조회/제거한다. 두 가지 경로가 있고 **같은 함수**(`paid_gate.list_paid_subscribers`/
  `add_paid_subscriber`/`remove_paid_subscribers`)를 공유하므로 결과가 어긋나지 않는다:
  - **관리자 페이지(로컬 실행 불필요)**: 배포된 대시보드 URL에 **`?admin=1`** 을 붙이면(`https://…/?admin=1`)
    관리자 페이지(`admin_page.py`)가 뜬다 — 일반 방문자의 사이드바/네비게이션에는 전혀 노출되지 않고,
    URL을 알아도 **`ADMIN_PASSWORD`** 비밀번호를 통과해야 기능이 보인다. 비밀번호 설정:
    `python3 -c "import secrets; print(secrets.token_urlsafe(16))"` → `secrets.json`의 `admin_password`
    또는 `ADMIN_PASSWORD` 환경변수(클라우드 배포용, HF Spaces Settings→Secrets)에 등록. 미설정 시
    관리자 페이지 자체가 비활성화된다. 기능: 명단 조회(이메일 **검색** + **CSV 내려받기**),
    직접 추가/**CSV 일괄 업로드**(둘 다 **만료일** 선택 지정 가능), 제거.
  - **한시적 접근(만료일)**: 추가 시 만료일(`EXPIRES_AT`, YYYY-MM-DD)을 지정하면 그날까지만 접근이
    유효하다(예: 체험판·수동 환불 유예). 비우면 영구(Stripe 구독자는 항상 영구). `paid_gate.is_paid_email`이
    리스트 멤버십과 함께 만료일을 검사하므로(만료일 없음=영구, 파싱 불가=영구로 안전하게 처리) 만료된
    구독자는 쿠키가 남아 있어도 다음 요청에서 즉시 차단된다 — 별도 스케줄러가 필요 없다. `EXPIRES_AT`는
    커스텀 속성이라 **`scripts/ensure_brevo_attributes.py`를 한 번 실행**해 스키마를 등록해 둬야 저장된다
    (미등록 커스텀 속성은 Brevo가 조용히 무시).
  - **로컬 CLI**(스크립팅/일괄 등록에 편리):
    ```bash
    .venv/bin/python scripts/manage_paid_subscribers.py list                 # 현재 유료 구독자 조회
    .venv/bin/python scripts/manage_paid_subscribers.py add <이메일...>       # 직권 등록
    .venv/bin/python scripts/manage_paid_subscribers.py remove <이메일...>    # 제거
    ```
- **구독 신청 폼**(대시보드 상단): 무료 뉴스레터 구독과 유료판 얼리버드 대기(평생 할인)를 한 폼에서 선택해
  신청할 수 있다(`waitlist.py`) — 각각 Brevo `BREVO_FREE_LIST_ID`/`BREVO_WAITLIST_LIST_ID` 리스트에 등록된다.
- **결제 자동화(Polar/Stripe → Brevo)**: `webhook/`의 Cloudflare Worker가 결제 완료 웹훅을 받아
  구매자 이메일을 Brevo 유료 리스트에 자동으로 추가한다 — `secrets.json`을 구독자마다 수동으로 고칠 필요가 없다.
  설정 방법은 [`webhook/README.md`](webhook/README.md) 참고. 미설정 시에는 `secrets.json`의
  `paid_access_codes`(대시보드 백업 코드)로 수동 운영할 수 있다. 클라우드 배포(HF Spaces/Streamlit Cloud)에는
  `secrets.json`이 없으므로 `PAID_ACCESS_CODES` 등은 동명의 환경변수(쉼표로 여러 개 구분)로 등록한다.
- **뉴스레터**: `newsletter.py` 가 매주 무료판(`_free`)과 유료판(`_paid`) 두 벌을 생성한다. 무료판은 미리보기
  구간만 공개하고 나머지 개수를 안내, 유료판은 통과 종목 전체를 공개한다. 발송 시 각 티어별로 Brevo가
  설정돼 있으면 그 리스트로 자동 발송(신규 구독자·결제자도 자동 포함)하고, 없으면 `secrets.json`의
  `subscribers`(무료판)/`paid_subscribers`(유료판) 수동 명단으로 SMTP 발송한다.
- **유니버스 추가 요청**: 포트폴리오 건강검진에서 분석 대상에 없는 티커를 조회하면 이메일로 추가를
  요청할 수 있다(`waitlist.request_ticker`, Brevo `brevo_universe_list_id` 리스트) — 접수 시 관리자
  계정으로 알림 메일도 발송된다. 관리자는 아래 명령으로 요청을 검토·반영한다:
  ```bash
  .venv/bin/python scripts/process_universe_requests.py            # 리포트만 (dry-run)
  .venv/bin/python scripts/process_universe_requests.py --apply    # config.py 반영 + Brevo 처리완료 표시 + 요청자 안내메일
  ```
  yfinance/pykrx로 실제 존재하는 종목인지 검증한 뒤에만 `US_UNIVERSE`/`KR_WATCHLIST`/`JP_UNIVERSE`에
  추가한다. 한국 종목은 해자(moat_tag)를 자동 추정하지 않고 `"none"` + `TODO` 주석으로 남겨 사람이
  나중에 검증하도록 한다. 로컬 `--apply` 후에는 `git diff`로 확인하고 커밋/푸시할 것.
  **자동화**: `.github/workflows/universe-requests.yml`가 (1) 매주 주간 스캔 직후 dry-run 리포트를
  Actions 요약에 남기고, (2) 수동 실행(`Run workflow → apply=true`) 시 신규 티커를 `config.py`에
  넣어 **PR을 연다**(직접 push 아님). 사람이 PR diff를 검토·머지하면, 다음 실행에서 해당 요청자에게
  자동으로 추가 안내 메일이 발송된다(2단계 — 머지 전 잘못된 안내를 막기 위함).
  ⚠️ Brevo는 스키마에 없는 커스텀 속성을 조용히 무시한다 — 새 Brevo 계정으로 다시 설정할 때는
  `scripts/ensure_brevo_attributes.py`를 한 번 실행해 `REQUESTED_TICKER`/`JOINED_AT`/`EARLYBIRD`/
  `PROCESSED`/`VALIDATION` 속성 스키마를 먼저 만들어야 한다.

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

## ☁️ 웹 배포 (로컬 분석 → 클라우드 표시)

**핵심 설계**: 무거운 수집·분석은 **로컬(한국 IP)**에서 돌리고, 클라우드엔 그 **결과 파일만** 읽는
가벼운 대시보드를 올린다. → 클라우드는 yfinance/pykrx 를 호출하지 않으므로
**레이트리밋·한국 차단·속도 문제가 없다.**

```
[로컬] publish.py → published/screening_data.json → git push
                                   │
[클라우드] app.py (DHANDHO_MODE=published) ─ 파일만 읽어 렌더 (네트워크 호출 0)
```

1. **로컬에서 데이터 내보내기 → push**
   ```bash
   .venv/bin/python publish.py        # 전체 스캔 → published/screening_data.json
   git add published/ && git commit -m "data: publish" && git push
   ```
2. **Streamlit Community Cloud 배포** (무료)
   - [share.streamlit.io](https://share.streamlit.io) → GitHub 로그인 → New app
   - Repo `sosmos3218-bot/dhandho-screener-claude` · Branch `main` · Main file `app.py`
   - **Advanced settings → Secrets** 에 한 줄 추가 (이게 배포 모드 스위치):
     ```toml
     DHANDHO_MODE = "published"
     ```
   - Deploy → `https://....streamlit.app` 공개 URL 발급
3. **주간 자동 갱신**: `.github/workflows/weekly.yml`(GitHub Actions, 매주 월 08:00 KST)이
   전체 스캔(US+KR+JP)·스냅샷·퍼블리시·뉴스레터(무료/유료 Brevo 자동발송)까지 전부 클라우드에서 실행하고,
   `published/`·`snapshots/`를 GitHub(origin)에 커밋한 뒤 `HF_TOKEN`으로 Hugging Face Space에도 push한다.
   로컬 PC/launchd 의존성 없음 — 2026-07-06 `test-cloud-scan.yml`로 pykrx/yfinance가 GitHub의
   해외 IP에서도 실전 규모(한국 11/11, 미국 40/40)로 정상 동작함을 실측 검증 후 전환했다.
   수동 실행(Actions 탭 → weekly-dhandho-full-scan → Run workflow)도 가능하며, `send_newsletter` 입력을
   `false`(기본값)로 두면 실제 발송 없이 스캔/퍼블리시만 테스트할 수 있다.

> ⚠️ **규제 주의**: 공개 서비스로 불특정 다수에 제공 시 한국에선 **유사투자자문업 신고** 대상이 될 수 있고,
> 데이터 상업이용 라이선스도 확인이 필요합니다. 지인·테스터 공유 수준이면 "정보·교육용" 면책 유지로 리스크가 낮습니다.

## 🔄 새 PC 복구 (로컬 PC 고장 시)

GitHub에 코드·데이터가 다 있으므로 새 Mac에서 아래로 완전 복원된다.

```bash
git clone https://github.com/sosmos3218-bot/dhandho-screener-claude.git dhandho-screener
cd dhandho-screener
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # ① 환경 재생성

# ② (선택) 로컬에서 직접 실행/디버깅하려면 secrets.json 필요 — secrets 는 보안상 깃에 없음
cp secrets.example.json secrets.json     # 편집: Brevo API 키 등
```

**주간 자동 실행은 GitHub Actions(`weekly.yml`)가 담당하므로 새 PC에서 별도로 launchd를 다시 등록할
필요가 없다.** `deploy/com.user.dhandho-snapshot.plist`는 2026-07-06 GitHub Actions 이전 후 로컬에서
`launchctl bootout`으로 비활성화된 옛 방식의 백업 파일로만 남아있다(비상시 로컬 재등록용, 평소엔 불필요).

**깃에 없는(=재생성 필요) 항목**: `.venv`(=pip 재설치) · `secrets.json`(=로컬 디버깅용, 재입력 필요 시만) ·
GitHub Actions Secrets(BREVO_*, HF_TOKEN — 저장소 Settings에 이미 등록되어 있으면 새 PC와 무관하게 그대로 동작).

## 파일 구성

| 파일 | 역할 |
|------|------|
| `config.py` | 임계값·가중치·미국 유니버스·한국 워치리스트(수동 INPUT)·해자 태그 |
| `data.py` | LIVE 수집 (yfinance / pykrx) + 디스크 캐시 |
| `screening.py` | Dhandho 지표·점수·플래그 계산, `build_universe()` |
| `app.py` | Streamlit 대시보드 (필터·KPI·테이블·차트·레이더·스냅샷 diff). URL에 `?admin=1` 이면 관리자 페이지로 분기 |
| `admin_page.py` | 관리자 페이지(`?admin=1` + `ADMIN_PASSWORD`) — 유료 구독자 조회/추가/제거, CLI와 동일 로직 |
| `snapshot.py` | 주간 스냅샷 + 신규/탈락 diff 생성 (`df` 주입 가능) |
| `publish.py` | 분석 결과 → `published/screening_data.json` (클라우드용) |
| `newsletter.py` | 스냅샷 → 무료/유료 뉴스레터 HTML+MD 생성 + Brevo 자동발송(폴백: SMTP) |
| `weekly_run.py` | 1회 스캔 → 스냅샷+퍼블리시+뉴스레터(+발송). GitHub Actions(`weekly.yml`)의 실행 진입점 |
| `.github/workflows/weekly.yml` | **주간 자동 갱신 진입점(현재 방식)** — GitHub Actions에서 전체 파이프라인 실행 + GitHub/HF 커밋 |
| `.github/workflows/test-cloud-scan.yml` | pykrx/yfinance가 GitHub Actions IP에서 막히는지 확인하는 수동 진단 워크플로 |
| `app.py` (DHANDHO_MODE=published) | 클라우드 배포 모드 — published 파일만 읽어 렌더 |
| `.streamlit/config.toml` · `published/` | 배포 설정 · 클라우드가 읽는 데이터 |
| `secrets.example.json` | Brevo/SMTP/구독자 설정 템플릿 (`secrets.json` 으로 복사해 로컬 실행 시 사용) |
| `snapshot_cron.sh`, `deploy/com.user.dhandho-snapshot.plist` | **레거시(비활성화됨)** — GitHub Actions 이전 전 로컬 launchd 방식의 흔적, 평소엔 불필요 |
| `SKILL.md` | 주간 스케줄 자동 리포트 정의 |
| `snapshots/` · `newsletter/` | 스냅샷·뉴스레터 산출물 누적 |

## 자동 업데이트

- **접속 시 라이브**: Streamlit `@st.cache_data`(TTL 12h) + 디스크 캐시로 최신화. 사이드바 "새로고침"으로 강제 갱신.
- **주간 파이프라인 (GitHub Actions, 매주 월 08:00 KST)**: `.github/workflows/weekly.yml`이 GitHub의
  클라우드 러너에서 `weekly_run.py`를 실행 → ① 전체 유니버스(US+KR+JP) 재스캔 → 스냅샷·diff 저장,
  ② 무료/유료 뉴스레터 HTML+MD 생성, ③ `BREVO_*` GitHub Secrets로 Brevo 자동발송,
  ④ `published/`·`snapshots/` 변경분을 GitHub(origin)에 커밋, ⑤ `HF_TOKEN`으로 Hugging Face Space에도 push
  (재시도 3회 포함). 로컬 PC가 꺼져 있어도 항상 실행된다.
  - 수동 실행: Actions 탭 → `weekly-dhandho-full-scan` → **Run workflow** →
    `send_newsletter`를 `false`(기본값)로 두면 실제 발송 없이 스캔/퍼블리시만 테스트, `true`면 실제 발송.
  - 필요한 GitHub Secrets: `BREVO_API_KEY`, `BREVO_PAID_LIST_ID`, `BREVO_FREE_LIST_ID`,
    `BREVO_SENDER_EMAIL`, `BREVO_SENDER_NAME`, `HF_TOKEN`(Hugging Face settings/tokens에서 Write 권한 발급).
  - 2026-07-06까지는 로컬 `weekly_run.py`를 launchd(매주 월 08:00)로 직접 실행했으나,
    `test-cloud-scan.yml`로 GitHub Actions의 해외 IP에서도 pykrx/yfinance가 실전 규모로 안 막힘을
    실측 검증한 뒤 위 방식으로 완전히 이전했다. 로컬 launchd는 `launchctl bootout`으로 비활성화됨
    (`deploy/com.user.dhandho-snapshot.plist`는 비상용 백업으로만 남겨둠).
  - 실행 로그: GitHub Actions 탭의 각 실행 로그 (레거시 로컬 로그는 `logs/launchd.{out,err}.log`)

## 📧 주간 뉴스레터

스냅샷을 읽기 좋은 뉴스레터로 자동 발행한다. **규제 안전을 위해 "매수 추천"이 아니라
정량 기준 통과 목록 + 교육적 해설** 형식이며, 모든 발행물에 비투자권유 면책을 포함한다.
무료판/유료판 두 벌을 함께 생성한다.

```bash
.venv/bin/python newsletter.py          # 생성만 → newsletter/dhandho_YYYY-MM-DD_{free,paid}.{html,md}
.venv/bin/python newsletter.py --send   # 생성 + SMTP 발송 (secrets.json 필요)
```

- **파일 생성(기본)**: `newsletter/` 에 무료판(`_free`)·유료판(`_paid`) 각각 HTML(이메일/플랫폼용, 인라인 스타일)과
  마크다운(스티비/Substack 붙여넣기용) 생성. 무료판은 Dhandho 점수 상위 `FREE_TIER_LIMIT`개만 공개하고
  나머지 개수를 안내, 유료판은 통과 종목 전체를 공개한다.
- **이메일 발송(opt-in)**: `secrets.example.json` → `secrets.json` 으로 복사 후 SMTP 정보·구독자 입력 시 활성화.
  - `subscribers` 목록에는 무료판을, `paid_subscribers` 목록에는 유료판을 발송한다.
  - Gmail: 2단계 인증 후 **앱 비밀번호**([myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)) 발급해 넣기. 네이버는 메일 환경설정에서 SMTP 사용 설정.
  - `secrets.json` 은 `.gitignore` 로 제외됨 (절대 커밋 금지).
- 내용: 시장 온도(통과 비율 기반 코멘트) · 신규 진입/탈락 · 통과 종목 표(무료판 Top N / 유료판 전체) · 주차별 로테이션 교육 코너 · 면책.

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
