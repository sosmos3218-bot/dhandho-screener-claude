# -*- coding: utf-8 -*-
"""
Dhandho 스크리닝 엔진
=====================
data.py 의 표준 dict → Dhandho 4개 축 지표 + 점수(0~100) + 통과/경고 플래그.

4개 축
  ① 시총 대비 현금흐름 : FCF Yield, P/FCF
  ② 낮은 부채          : Debt/Equity, NetDebt/EBITDA
  ③ 독점적 해자(Moat)  : ROIC, 매출총이익률, 영업이익률 안정성 + 정성 태그
  ④ 저평가/안전마진     : P/E, P/B, Earnings Yield(EBIT/EV)

각 축을 임계값 기준 0~1 로 정규화 → 가중합 ×100 = Dhandho Score.
"""
import datetime as dt

import pandas as pd

import config
import data

TH = config.THRESHOLDS
W = config.SCORE_WEIGHTS


# ──────────────────────────────────────────────────────────────────────────
# 정규화 헬퍼 (0~1)
# ──────────────────────────────────────────────────────────────────────────
def _norm_higher(v, target, floor=0.0):
    """클수록 좋은 지표. target 에서 1.0, floor 에서 0.0 (그 이상은 1.0 clip)."""
    if v is None:
        return 0.0
    if v >= target:
        return 1.0
    if v <= floor:
        return 0.0
    return (v - floor) / (target - floor)


def _norm_lower(v, target, ceil):
    """작을수록 좋은 지표. target 이하면 1.0, ceil 이상이면 0.0."""
    if v is None:
        return 0.0
    if v <= target:
        return 1.0
    if v >= ceil:
        return 0.0
    return (ceil - v) / (ceil - target)


# ──────────────────────────────────────────────────────────────────────────
# 지표 계산
# ──────────────────────────────────────────────────────────────────────────
def build_row(raw: dict) -> dict:
    """표준 raw dict → Dhandho 지표 + 점수 + 플래그가 채워진 행."""
    r = dict(raw)  # 원본 보존
    mc = raw.get("market_cap")
    fcf = raw.get("fcf")
    ev = raw.get("enterprise_value")
    ebit = raw.get("ebit")
    ebitda = raw.get("ebitda")
    equity = raw.get("equity")
    debt = raw.get("total_debt")
    net_debt = raw.get("net_debt")

    # ① 현금흐름
    r["fcf_yield"] = (fcf / mc * 100.0) if (fcf and mc and mc > 0) else None
    r["p_fcf"] = (mc / fcf) if (fcf and mc and fcf > 0) else None

    # ② 부채
    r["debt_equity"] = (debt / equity) if (debt is not None and equity and equity > 0) else None
    r["netdebt_ebitda"] = (net_debt / ebitda) if (net_debt is not None and ebitda and ebitda > 0) else None

    # ③ 해자 (roic, gross_margin, op_margin_std 는 raw 에 이미 있음)
    # ④ 저평가
    r["earnings_yield"] = (ebit / ev * 100.0) if (ebit and ev and ev > 0) else None

    # 축별 점수(0~1)
    s_cf = (_norm_higher(r["fcf_yield"], TH["fcf_yield_min"]) * 0.6
            + _norm_lower(r["p_fcf"], TH["p_fcf_max"], TH["p_fcf_max"] * 3) * 0.4)

    s_debt = (_norm_lower(r["debt_equity"], TH["debt_equity_max"], TH["debt_equity_max"] * 4) * 0.6
              + _norm_lower(r["netdebt_ebitda"], TH["netdebt_ebitda_max"], TH["netdebt_ebitda_max"] * 3) * 0.4)

    s_moat_quant = (_norm_higher(r.get("roic"), TH["roic_min"]) * 0.5
                    + _norm_higher(r.get("gross_margin"), TH["gross_margin_min"]) * 0.3
                    + _norm_lower(r.get("op_margin_std"), TH["margin_stability_max"], TH["margin_stability_max"] * 3) * 0.2)
    moat_bonus = config.MOAT_TAG_BONUS.get(r.get("moat_tag", "none"), 0.0)
    s_moat = min(1.0, s_moat_quant + moat_bonus)

    s_value = (_norm_lower(r.get("pe"), TH["pe_max"], TH["pe_max"] * 3) * 0.4
               + _norm_lower(r.get("pb"), TH["pb_max"], TH["pb_max"] * 3) * 0.3
               + _norm_higher(r["earnings_yield"], TH["earnings_yield_min"]) * 0.3)

    r["score_cashflow"] = round(s_cf * 100, 1)
    r["score_debt"] = round(s_debt * 100, 1)
    r["score_moat"] = round(s_moat * 100, 1)
    r["score_value"] = round(s_value * 100, 1)
    r["dhandho_score"] = round(
        (W["cashflow"] * s_cf + W["debt"] * s_debt
         + W["moat"] * s_moat + W["value"] * s_value) * 100, 1)

    # "Heads I win, tails I don't lose much" 하방 방어 게이지(0~100, 높을수록 안전)
    r["downside_score"] = round(
        (_norm_lower(r["debt_equity"], TH["debt_equity_max"], TH["debt_equity_max"] * 4) * 0.4
         + _norm_lower(r["netdebt_ebitda"], TH["netdebt_ebitda_max"], TH["netdebt_ebitda_max"] * 3) * 0.3
         + _norm_higher(r["fcf_yield"], TH["fcf_yield_min"]) * 0.3) * 100, 1)

    # 통과/경고 플래그
    r["flags"] = _flags(r)
    r["passes"] = _passes_filters(r)
    return r


def _flags(r: dict) -> list:
    """충족한 조건 라벨 목록 (UI 뱃지용)."""
    f = []
    if r.get("fcf_yield") is not None and r["fcf_yield"] >= TH["fcf_yield_min"]:
        f.append("💰현금흐름")
    if r.get("debt_equity") is not None and r["debt_equity"] <= TH["debt_equity_max"]:
        f.append("🛡️저부채")
    if (r.get("roic") is not None and r["roic"] >= TH["roic_min"]) or r.get("moat_tag") == "wide":
        f.append("🏰해자")
    if (r.get("pe") is not None and r["pe"] <= TH["pe_max"]) or \
       (r.get("earnings_yield") is not None and r["earnings_yield"] >= TH["earnings_yield_min"]):
        f.append("🎯저평가")
    return f


def _passes_filters(r: dict, strict: bool = False) -> bool:
    """
    Dhandho 핵심 4축 통과 여부.
      기본(strict=False): 4축 중 최소 3축 충족 + 부채 축은 필수.
      strict=True: 4축 전부 충족.
    """
    cf_ok = r.get("fcf_yield") is not None and r["fcf_yield"] >= TH["fcf_yield_min"]
    debt_ok = r.get("debt_equity") is not None and r["debt_equity"] <= TH["debt_equity_max"]
    moat_ok = (r.get("roic") is not None and r["roic"] >= TH["roic_min"]) or r.get("moat_tag") == "wide"
    value_ok = (r.get("pe") is not None and r["pe"] <= TH["pe_max"]) or \
               (r.get("earnings_yield") is not None and r["earnings_yield"] >= TH["earnings_yield_min"])
    axes = [cf_ok, debt_ok, moat_ok, value_ok]
    if strict:
        return all(axes)
    return debt_ok and sum(axes) >= 3


# ──────────────────────────────────────────────────────────────────────────
# 유니버스 빌드
# ──────────────────────────────────────────────────────────────────────────
def build_universe(market: str = "ALL", ref: dt.date = None,
                   use_cache: bool = True, limit: int = None) -> pd.DataFrame:
    """
    market: 'US' | 'KR' | 'ALL'
    반환: Dhandho 지표·점수·플래그가 채워진 DataFrame (dhandho_score 내림차순).
    """
    ref = ref or dt.date.today()
    rows = []

    if market in ("US", "ALL"):
        tickers = config.all_us()
        if limit:
            tickers = tickers[:limit]
        for t in tickers:
            raw = data.fetch_us(t, use_cache=use_cache)
            if raw.get("error"):
                continue
            rows.append(build_row(raw))

    if market in ("KR", "ALL"):
        for t, info in config.all_kr():
            raw = data.fetch_kr(t, info, ref=ref, use_cache=use_cache)
            rows.append(build_row(raw))

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return df.sort_values("dhandho_score", ascending=False).reset_index(drop=True)


# 화면/스냅샷용 컬럼 순서
DISPLAY_COLS = [
    "market", "ticker", "name", "moat_tag", "dhandho_score",
    "fcf_yield", "p_fcf", "debt_equity", "netdebt_ebitda",
    "roic", "gross_margin", "op_margin_std",
    "pe", "pb", "earnings_yield",
    "score_cashflow", "score_debt", "score_moat", "score_value",
    "downside_score", "passes", "flags",
]
