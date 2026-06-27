# -*- coding: utf-8 -*-
"""
데이터 계층 (LIVE)
==================
  미국: yfinance 로 시가총액·FCF·부채·ROIC·마진·PER·PBR 자동 수집
  한국: pykrx 로 가격(LIVE) 수집 + config.py 의 수동 펀더멘털 결합

설계 원칙
  - 모든 fetch_* 는 *시장 무관 표준 dict* 를 반환 (screening.py 에서 일관 처리)
  - yfinance 는 비공식 스크레이퍼 → 디스크 캐시(JSON) + graceful skip 으로 방어
  - 결측값은 None 으로 남기고 점수 계산 시 보수적으로 처리
"""
import datetime as dt
import json
import time
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

import config  # noqa: E402

_CACHE_DIR = Path(__file__).parent / ".cache"
_CACHE_DIR.mkdir(exist_ok=True)
_CACHE_TTL_HOURS = 12          # 디스크 캐시 유효 시간
_DATE_FMT = "%Y%m%d"
_DEFAULT_TAX_RATE = 0.21       # ROIC NOPAT 추정용 실효세율


# ──────────────────────────────────────────────────────────────────────────
# 디스크 캐시
# ──────────────────────────────────────────────────────────────────────────
def _cache_path(key: str) -> Path:
    safe = key.replace("/", "_").replace(".", "_")
    return _CACHE_DIR / f"{safe}.json"


def _cache_get(key: str):
    p = _cache_path(key)
    if not p.exists():
        return None
    try:
        payload = json.loads(p.read_text())
        ts = dt.datetime.fromisoformat(payload["_ts"])
        if dt.datetime.now() - ts > dt.timedelta(hours=_CACHE_TTL_HOURS):
            return None
        return payload["data"]
    except Exception:
        return None


def _cache_set(key: str, data: dict):
    try:
        _cache_path(key).write_text(
            json.dumps({"_ts": dt.datetime.now().isoformat(), "data": data},
                       ensure_ascii=False)
        )
    except Exception:
        pass


def clear_cache():
    for p in _CACHE_DIR.glob("*.json"):
        p.unlink(missing_ok=True)


# ──────────────────────────────────────────────────────────────────────────
# 유틸
# ──────────────────────────────────────────────────────────────────────────
def _num(v):
    """숫자로 안전 변환 (None/NaN/0 구분 유지)."""
    try:
        if v is None:
            return None
        f = float(v)
        if pd.isna(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _row_value(df: pd.DataFrame, names, col=0):
    """재무제표 DataFrame 에서 여러 후보 행 이름 중 첫 매칭값(col번째 열) 반환."""
    if df is None or df.empty:
        return None
    for n in names:
        if n in df.index:
            try:
                return _num(df.loc[n].iloc[col])
            except Exception:
                continue
    return None


# ──────────────────────────────────────────────────────────────────────────
# 미국: yfinance
# ──────────────────────────────────────────────────────────────────────────
def _yf_raw(yf_ticker: str, market: str) -> dict:
    """
    yfinance 한 종목 → 표준 dict. 미국/한국(.KS/.KQ) 공통 코어.
    PE/PB 는 info 값이 없으면(특히 KRX) None 으로 두고, 호출부에서
    시총/순이익/자본으로 직접 계산한다. net_income·invested_capital·shares 도 함께 반환.
    """
    import yfinance as yf

    out = _empty_row(yf_ticker, market)
    try:
        tk = yf.Ticker(yf_ticker)
        info = tk.info or {}
    except Exception as e:
        out["error"] = f"info 실패: {e}"
        return out

    out["name"] = info.get("shortName") or info.get("longName") or yf_ticker
    out["currency"] = info.get("currency", "USD" if market == "US" else "KRW")
    out["price"] = _num(info.get("currentPrice") or info.get("regularMarketPrice"))
    out["market_cap"] = _num(info.get("marketCap"))
    out["enterprise_value"] = _num(info.get("enterpriseValue"))
    out["pe"] = _num(info.get("trailingPE"))
    out["pb"] = _num(info.get("priceToBook"))
    out["ebitda"] = _num(info.get("ebitda"))
    out["total_debt"] = _num(info.get("totalDebt"))
    out["total_cash"] = _num(info.get("totalCash"))
    out["roe"] = _pct(info.get("returnOnEquity"))
    out["gross_margin"] = _pct(info.get("grossMargins"))
    out["op_margin"] = _pct(info.get("operatingMargins"))
    out["shares"] = _num(info.get("sharesOutstanding"))

    fcf = _num(info.get("freeCashflow"))
    rev = _num(info.get("totalRevenue"))

    # 재무제표 (다년) — 결측/예외 graceful
    cf = bs = fin = None
    try:
        cf = tk.cashflow
    except Exception:
        pass
    try:
        bs = tk.balance_sheet
    except Exception:
        pass
    try:
        fin = tk.financials
    except Exception:
        pass

    # FCF: info 우선, 없으면 영업CF − CapEx 직접 계산
    if fcf is None:
        ocf = _row_value(cf, ["Operating Cash Flow", "Total Cash From Operating Activities"])
        capex = _row_value(cf, ["Capital Expenditure", "Capital Expenditures"])
        if ocf is not None and capex is not None:
            fcf = ocf + capex  # capex 는 음수로 저장됨
    out["fcf"] = fcf

    # 자본 / 투하자본 / 순부채
    out["equity"] = _row_value(bs, ["Common Stock Equity", "Stockholders Equity",
                                    "Total Equity Gross Minority Interest"])
    out["invested_capital"] = _row_value(bs, ["Invested Capital", "Total Capitalization"])
    net_debt_bs = _row_value(bs, ["Net Debt"])
    if out["total_debt"] is None:
        out["total_debt"] = _row_value(bs, ["Total Debt"])
    if net_debt_bs is not None:
        out["net_debt"] = net_debt_bs
    elif out["total_debt"] is not None and out["total_cash"] is not None:
        out["net_debt"] = out["total_debt"] - out["total_cash"]

    # EBIT (Earnings Yield + ROIC 용) / 순이익(PE 계산용)
    ebit = _row_value(fin, ["EBIT", "Operating Income", "Total Operating Income As Reported"])
    if ebit is None and out["op_margin"] is not None and rev is not None:
        ebit = rev * out["op_margin"] / 100.0
    out["ebit"] = ebit
    out["net_income"] = _row_value(fin, ["Net Income", "Net Income Common Stockholders",
                                         "Net Income From Continuing Operation Net Minority Interest"])

    # ROIC = NOPAT / Invested Capital (없으면 ROE 폴백)
    if ebit is not None and out["invested_capital"] not in (None, 0):
        out["roic"] = ebit * (1 - _DEFAULT_TAX_RATE) / out["invested_capital"] * 100.0
    else:
        out["roic"] = out["roe"]

    out["op_margin_std"] = _op_margin_std(fin)
    return out


def fetch_us(ticker: str, use_cache: bool = True) -> dict:
    """미국 종목 표준 dict. 실패/결측은 None 필드로."""
    if use_cache:
        cached = _cache_get(f"us_{ticker}")
        if cached is not None:
            return cached
    out = _yf_raw(ticker, "US")
    out["moat_tag"] = config.moat_tag_us(ticker)
    if use_cache and not out.get("error"):
        _cache_set(f"us_{ticker}", out)
    time.sleep(0.2)  # 다수 티커 스캔 시 레이트리밋 완화
    return out


def _op_margin_std(fin: pd.DataFrame):
    """다년 영업이익률(영업이익/매출) 표준편차(%p)."""
    if fin is None or fin.empty:
        return None
    rev_names = ["Total Revenue", "Operating Revenue"]
    op_names = ["EBIT", "Operating Income", "Total Operating Income As Reported"]
    rev_row = next((fin.loc[n] for n in rev_names if n in fin.index), None)
    op_row = next((fin.loc[n] for n in op_names if n in fin.index), None)
    if rev_row is None or op_row is None:
        return None
    margins = []
    for col in fin.columns:
        r = _num(rev_row.get(col))
        o = _num(op_row.get(col))
        if r and o is not None and r != 0:
            margins.append(o / r * 100.0)
    if len(margins) < 2:
        return None
    return float(pd.Series(margins).std())


def _pct(v):
    """yfinance 비율(0~1) → % 변환."""
    n = _num(v)
    return n * 100.0 if n is not None else None


def _empty_row(ticker: str, market: str) -> dict:
    return {
        "ticker": ticker, "market": market, "name": ticker, "currency": "",
        "price": None, "market_cap": None, "enterprise_value": None,
        "fcf": None, "total_debt": None, "total_cash": None, "net_debt": None,
        "equity": None, "ebitda": None, "ebit": None,
        "roic": None, "roe": None, "gross_margin": None,
        "op_margin": None, "op_margin_std": None,
        "pe": None, "pb": None, "moat_tag": "none",
        "net_income": None, "invested_capital": None, "shares": None,
        "as_of": None, "source": None, "error": None,
    }


# ──────────────────────────────────────────────────────────────────────────
# 한국: pykrx 가격(LIVE) + config 수동 펀더멘털
# ──────────────────────────────────────────────────────────────────────────
def _kr_latest_close(ticker: str, ref: dt.date):
    """기준일 이전 최근 종가. (close, date) 또는 (None, None).
    kospi-bubble-dashboard/data.py 의 latest_close 패턴 재사용."""
    from pykrx import stock
    start = (ref - dt.timedelta(days=12)).strftime(_DATE_FMT)
    end = ref.strftime(_DATE_FMT)
    try:
        df = stock.get_market_ohlcv_by_date(start, end, ticker)
    except Exception:
        return None, None
    if df is None or len(df) == 0:
        return None, None
    return float(df["종가"].iloc[-1]), df.index[-1].date()


def fetch_kr(ticker: str, info: dict, ref: dt.date = None, use_cache: bool = True) -> dict:
    """
    한국 종목 표준 dict.
      - 펀더멘털(FCF·부채·자본·EBITDA·EBIT·순이익·ROIC·마진): yfinance .KS/.KQ 자동 수집
      - 가격(LIVE): pykrx (KOSPI/KOSDAQ 모두 안정) → 없으면 yfinance 폴백
      - 시가총액: LIVE 가격 × 발행주식수 (가장 최신)
      - PER/PBR: 시총÷순이익, 시총÷자본 으로 직접 계산
      - yfinance 결측 필드는 config.py 수동값(info)으로 폴백
    """
    ref = ref or dt.date.today()
    cache_key = f"kr_{ticker}"
    if use_cache:
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

    out = _empty_row(ticker, "KR")
    out["name"] = info.get("name", ticker)
    out["currency"] = "KRW"
    out["moat_tag"] = info.get("moat_tag", "none")
    out["as_of"] = info.get("as_of")
    out["source"] = info.get("source")

    # yfinance 펀더멘털 (.KS=KOSPI / .KQ=KOSDAQ)
    yf_ticker = info.get("yf") or f"{ticker}.KS"
    raw = _yf_raw(yf_ticker, "KR")

    def pick(key, cfg_key=None):
        """yfinance 우선, 없으면 config 수동값."""
        v = raw.get(key)
        return v if v is not None else _num(info.get(cfg_key or key))

    # LIVE 가격: pykrx 우선, 실패 시 yfinance
    price, _ = _kr_latest_close(ticker, ref)
    if price is None:
        price = raw.get("price")
    out["price"] = price

    shares = raw.get("shares") or _num(info.get("shares"))
    if price and shares:
        out["market_cap"] = price * shares
    else:
        out["market_cap"] = raw.get("market_cap")

    out["fcf"] = pick("fcf")
    out["total_debt"] = pick("total_debt")
    out["total_cash"] = raw.get("total_cash")
    out["equity"] = pick("equity")
    out["ebitda"] = pick("ebitda")
    out["ebit"] = pick("ebit")
    out["gross_margin"] = pick("gross_margin")
    out["op_margin_std"] = pick("op_margin_std")
    net_income = raw.get("net_income")
    invested_capital = raw.get("invested_capital")

    # 순부채
    if out["total_debt"] is not None and out["total_cash"] is not None:
        out["net_debt"] = out["total_debt"] - out["total_cash"]
    else:
        out["net_debt"] = out["total_debt"]

    # ROIC: 투하자본 기반 → ROE → config 수동
    if out["ebit"] is not None and invested_capital not in (None, 0):
        out["roic"] = out["ebit"] * (1 - _DEFAULT_TAX_RATE) / invested_capital * 100.0
    elif raw.get("roe") is not None:
        out["roic"] = raw.get("roe")
    else:
        out["roic"] = _num(info.get("roic"))
    out["roe"] = raw.get("roe") if raw.get("roe") is not None else _num(info.get("roic"))

    # PER = 시총/순이익(폴백 가격/EPS), PBR = 시총/자본(폴백 가격/BPS)
    mc = out["market_cap"]
    eps, bvps = _num(info.get("eps")), _num(info.get("bvps"))
    if mc and net_income and net_income > 0:
        out["pe"] = mc / net_income
    elif price and eps and eps > 0:
        out["pe"] = price / eps
    if mc and out["equity"] and out["equity"] > 0:
        out["pb"] = mc / out["equity"]
    elif price and bvps and bvps > 0:
        out["pb"] = price / bvps

    # enterprise_value ≈ 시총 + 순부채
    if mc is not None and out["net_debt"] is not None:
        out["enterprise_value"] = mc + out["net_debt"]

    if use_cache:
        _cache_set(cache_key, out)
    time.sleep(0.2)
    return out
