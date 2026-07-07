#!/usr/bin/env python3
"""관리자용: '유니버스 미포함 종목' 추가 요청을 Brevo에서 읽어 config.py에 반영한다.

포트폴리오 건강검진에서 사용자가 요청한 티커(waitlist.request_ticker)는
Brevo 리스트(brevo_universe_list_id)에 REQUESTED_TICKER 속성으로 쌓인다.
이 스크립트는 그 요청들을 검증(yfinance/pykrx로 실제 존재하는 종목인지 확인)한 뒤
--apply 옵션을 주면 config.py의 US_UNIVERSE / KR_WATCHLIST / JP_UNIVERSE에 실제로 추가한다.

사용법:
  .venv/bin/python scripts/process_universe_requests.py            # 리포트만 (dry-run, Brevo/파일 무변경)
  .venv/bin/python scripts/process_universe_requests.py --apply    # 신규 티커 config.py 편집 + 완료건 요청자 안내 + 무효건 정리

2단계 처리 (PR 게이트와 정합):
  - 신규 유효 티커 → config.py만 편집한다. 아직 요청자에게 안내하지 않고 처리완료로도 표시하지 않는다
    (PR 머지 전엔 실제 반영이 아니므로). 이 변경은 PR로 올려 사람이 검토·머지한다.
  - 머지되면 다음 실행에서 그 티커가 already_covered로 잡혀 → 그때 요청자에게 "추가됨" 안내 + PROCESSED 표시.
  - 무효(실존하지 않는) 티커 → 즉시 PROCESSED + VALIDATION=invalid 로 정리(안내 없음).
  → PR을 거부(close)하면 티커는 계속 pending 상태로 남아 다음 리포트에 다시 노출된다.

주의:
  - 한국 종목은 moat_tag를 자동 추정하지 않고 "none" + TODO 주석으로 남긴다
    (이 프로젝트는 해자 태그를 사람이 검증하는 것을 원칙으로 한다. config.py 상단 주석 참고).
  - GitHub Actions(.github/workflows/universe-requests.yml)가 주간 dry-run 리포트 +
    수동 apply(PR 생성)를 자동화한다. 로컬 --apply 후에는 git diff로 확인하고 커밋/푸시할 것.
"""
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import brevo  # noqa: E402
import config  # noqa: E402
import data  # noqa: E402

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.py"


# ──────────────────────────────────────────────────────────────────────────
# Brevo
# ──────────────────────────────────────────────────────────────────────────
def _notify_requester(email: str, ticker: str) -> None:
    key = config.brevo_api_key()
    admin_email, sender_name = config.brevo_sender()
    if not key or not admin_email:
        return
    brevo.send_transactional_email(
        admin_email, sender_name, email,
        f"[Dhandho Screener] '{ticker}' 종목이 분석 대상에 추가되었습니다",
        f"<p>요청하신 종목 <b>{ticker}</b>이(가) 분석 대상 유니버스에 추가되었습니다. "
        f"다음 주간 스캔부터 반영됩니다.</p>",
        key,
    )


def fetch_pending_requests(list_id: str, key: str) -> list:
    """[{email, ticker}] — PROCESSED=true 인 컨택은 제외."""
    out = []
    for c in brevo.list_contacts_in_list(list_id, key):
        attrs = c.get("attributes", {}) or {}
        if attrs.get("PROCESSED"):
            continue
        ticker = str(attrs.get("REQUESTED_TICKER", "")).strip().upper()
        if ticker:
            out.append({"email": c.get("email"), "ticker": ticker})
    return out


# ──────────────────────────────────────────────────────────────────────────
# 분류 / 검증
# ──────────────────────────────────────────────────────────────────────────
def classify_market(ticker: str) -> str:
    if re.fullmatch(r"\d{6}", ticker):
        return "KR"
    if ticker.endswith(".T"):
        return "JP"
    return "US"


def already_covered(ticker: str, market: str) -> bool:
    if market == "US":
        return ticker in config.US_UNIVERSE
    if market == "JP":
        return ticker in config.JP_UNIVERSE
    if market == "KR":
        return ticker in config.KR_WATCHLIST
    return False


def validate_us(ticker: str):
    r = data.fetch_us(ticker, use_cache=False)
    if r.get("error") or not r.get("price"):
        return None
    return {"name": r.get("name") or ticker}


def validate_jp(ticker: str):
    r = data.fetch_jp(ticker, use_cache=False)
    if r.get("error") or not r.get("price"):
        return None
    return {"name": r.get("name") or ticker}


def _kr_suffix_by_market_list(code: str) -> str:
    """pykrx 시장 명단으로 KOSPI=.KS / KOSDAQ=.KQ 판별(휴장일 대비 최근 영업일 탐색). 실패 시 .KS.
    이 엔드포인트는 환경/일자에 따라 빈 값을 반환하기도 하므로 보조 수단으로만 쓴다."""
    try:
        from pykrx import stock
        for d in range(7):
            day = (datetime.now() - timedelta(days=d)).strftime("%Y%m%d")
            kosdaq = stock.get_market_ticker_list(day, market="KOSDAQ")
            if kosdaq:
                return ".KQ" if code in set(kosdaq) else ".KS"
    except Exception:
        pass
    return ".KS"


def _looks_like_real_name(name, code: str) -> bool:
    """yfinance가 '미상장 suffix'에 대해 돌려주는 쓰레기 이름(코드/펀드ID를 쉼표로 이어붙인 값,
    예: '247540.KS,0P0001GZPV,623889')을 걸러 진짜 종목명만 통과시킨다."""
    if not isinstance(name, str):
        return False
    n = name.strip()
    if not n:
        return False
    return code not in n and "," not in n and not n.endswith((".KS", ".KQ"))


def validate_kr(code: str):
    """pykrx가 종목명을 알면 실존하는 유효 종목으로 인정한다. 가격은 실제 스캔에서 pykrx로
    조달하므로(data.fetch_kr) yfinance 결측이어도 무효가 아니다 — yfinance 가격만으로 거르면
    yfinance 결측이 잦은 KOSDAQ 정상 종목이 조용히 버려진다(config.py:176 참고).
    yf suffix는 '정상 이름을 주는' 쪽을 우선 채택한다: yfinance는 오답 suffix에도 price를
    붙인 엉뚱한 증권을 돌려주므로(예: KOSDAQ 종목의 .KS), price 유무가 아니라 이름 품질로 고른다."""
    name = None
    try:
        from pykrx import stock
        name = stock.get_market_ticker_name(code)
    except Exception:
        pass
    # pykrx는 미상장/무효 코드에 대해 예외 대신 비문자열(빈 DataFrame 등)을 돌려주기도 하므로
    # 반드시 유효한 문자열인지 확인한다 — 아니면 무효로 처리(6자리 무효코드가 전체 실행을 깨지 않게).
    if not isinstance(name, str) or not name.strip():
        return None
    name = name.strip()

    good = []
    for suffix in (".KS", ".KQ"):
        r = data.fetch_us(f"{code}{suffix}", use_cache=False)
        if not r.get("error") and _looks_like_real_name(r.get("name"), code):
            good.append(suffix)
    if len(good) == 1:
        suffix = good[0]
    else:
        # 애매(둘 다 정상이거나 둘 다 불명) → 시장 명단으로 판별, 그래도 안 되면 .KS
        suffix = _kr_suffix_by_market_list(code)
    return {"name": name, "yf": f"{code}{suffix}"}


# ──────────────────────────────────────────────────────────────────────────
# config.py 반영 (텍스트 삽입 — 각 리스트/딕셔너리는 outer 닫는 괄호가
# 줄 맨 앞에 단독으로 오는 포맷이라 첫 "\n]"/"\n}" 를 안전하게 찾을 수 있다)
# ──────────────────────────────────────────────────────────────────────────
def apply_to_config(market: str, ticker: str, info: dict) -> None:
    text = CONFIG_PATH.read_text(encoding="utf-8")

    if market in ("US", "JP"):
        anchor = "US_UNIVERSE = [" if market == "US" else "JP_UNIVERSE = ["
        start = text.index(anchor)
        end = text.index("\n]", start)
        insertion = f'\n    "{ticker}",  # 자동 추가 (사용자 요청)'
        text = text[:end] + insertion + text[end:]
    elif market == "KR":
        anchor = "KR_WATCHLIST = {"
        start = text.index(anchor)
        end = text.index("\n}", start)
        insertion = (
            f'\n    "{ticker}": {{"name": "{info["name"]}", "yf": "{info["yf"]}", "moat_tag": "none"}},'
            f"  # TODO: 해자 태그·종목명·yf suffix(.KS/.KQ) 검증 필요 (자동 추가됨, 사용자 요청)"
        )
        text = text[:end] + insertion + text[end:]
    else:
        return

    CONFIG_PATH.write_text(text, encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────────
def main() -> int:
    apply = "--apply" in sys.argv
    key = config.brevo_api_key()
    list_id = config.brevo_universe_list_id()
    if not key or not list_id:
        print(json.dumps({"error": "brevo_api_key / brevo_universe_list_id 미설정"}))
        return 1

    pending = fetch_pending_requests(list_id, key)
    if not pending:
        print("처리할 요청 없음.")
        return 0

    by_ticker = {}
    for r in pending:
        by_ticker.setdefault(r["ticker"], []).append(r["email"])

    print(f"미처리 요청 {len(pending)}건, 고유 티커 {len(by_ticker)}개\n")

    edited, finalized, invalid = 0, 0, 0
    for ticker, emails in by_ticker.items():
        market = classify_market(ticker)

        if already_covered(ticker, market):
            # 이미 유니버스에 있음(수동으로 넣었거나, 직전 PR이 머지돼 이번 실행에 반영됨).
            # → 이제 요청자에게 "추가됨"을 안내하고 처리완료로 표시한다. (실제 반영이 끝난 시점)
            print(f"  [완료] {ticker} ({market}) — 유니버스에 반영됨, 요청자 안내 (요청 {len(emails)}건)")
            if apply:
                for e in emails:
                    brevo.update_contact(e, {"PROCESSED": True}, key)
                    _notify_requester(e, ticker)
                finalized += 1
            continue

        info = {"US": validate_us, "JP": validate_jp, "KR": validate_kr}[market](ticker)

        if info is None:
            print(f"  [무효] {ticker} ({market}) — 실제 종목 확인 실패 (요청자 {len(emails)}명)")
            if apply:
                for e in emails:
                    brevo.update_contact(e, {"PROCESSED": True, "VALIDATION": "invalid"}, key)
                invalid += 1
            continue

        # 신규 유효 종목 → config.py만 편집(PR 대상). 아직 PROCESSED/안내메일은 보내지 않는다:
        # PR 머지 전엔 실제 반영이 아니므로, 머지 후 다음 실행에서 already_covered로 잡혀 마무리된다.
        print(f"  [신규] {ticker} ({market}) — {info.get('name')} · config.py 편집(PR 대상), 요청 {len(emails)}건")
        if apply:
            apply_to_config(market, ticker, info)
            edited += 1

    if apply:
        print(f"\n반영 요약: config.py 신규 편집 {edited}건 · 요청자 안내(완료) {finalized}건 · 무효 정리 {invalid}건")
        if edited:
            print("→ config.py가 수정되었습니다. PR로 올려 검토·머지하세요 (머지 후 다음 실행에서 요청자에게 자동 안내).")
    else:
        print("\n(dry-run) 실제 반영하려면 --apply 옵션을 추가하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
