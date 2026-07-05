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

    # 보조 점수: codex(kospi_bubble_dashboard) 포인트 방식 (교차검증용, 통과 판정에는 미반영)
    r.update(_codex_score(raw))
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


def _codex_score(raw: dict) -> dict:
    """
    보조 점수: dhandho-korea-weekly-codex(kospi_bubble_dashboard) 방식의 포인트 합산 스코어.
    기존 4-axis 가중합(dhandho_score)과 별개로, 다른 임계값/가중치 관점의 교차검증용으로 병기한다.
      Cash 0~30(FCF Yield) + Debt 0~25(D/E·NetDebt/FCF·Cash/Debt) +
      Moat 0~100×0.25(태그+영업이익률+매출총이익률+ROIC) + Valuation 0~20(FCF Yield·P/E·EV/EBITDA)
      → 0~100, A(≥75)/B(≥60)/C(≥45)/D 밴드.
    """
    market_cap = raw.get("market_cap")
    fcf = raw.get("fcf")
    total_debt = raw.get("total_debt")
    total_cash = raw.get("total_cash")
    total_equity = raw.get("equity")
    ebitda = raw.get("ebitda")
    ev = raw.get("enterprise_value")
    pe = raw.get("pe")
    op_margin = raw.get("op_margin")      # %
    gross_margin = raw.get("gross_margin")  # %
    roic = raw.get("roic")                # %
    moat_tag = raw.get("moat_tag", "none")

    fcf_yield = (fcf / market_cap) if (fcf is not None and market_cap) else None
    debt_equity = (total_debt / total_equity) if (total_debt is not None and total_equity) else None
    net_debt = ((total_debt or 0) - (total_cash or 0)) if (total_debt is not None or total_cash is not None) else None
    net_debt_fcf = (net_debt / fcf) if (net_debt is not None and fcf and fcf > 0) else None
    cash_debt = (total_cash / total_debt) if (total_cash is not None and total_debt) else None
    ev_to_ebitda = (ev / ebitda) if (ev is not None and ebitda) else None

    cash_score = 0.0
    if fcf_yield is not None:
        if fcf_yield <= 0:
            cash_score = 0.0
        elif fcf_yield >= 0.15:
            cash_score = 30.0
        else:
            cash_score = min(30.0, fcf_yield / 0.15 * 30)

    debt_score = 10.0 if debt_equity is None and net_debt_fcf is None else 0.0
    if debt_equity is not None:
        if debt_equity <= 0.3:
            debt_score += 12
        elif debt_equity <= 0.8:
            debt_score += 9
        elif debt_equity <= 1.5:
            debt_score += 5
    if net_debt_fcf is not None:
        if net_debt_fcf <= 2:
            debt_score += 8
        elif net_debt_fcf <= 4:
            debt_score += 5
        elif net_debt_fcf <= 6:
            debt_score += 2
    if cash_debt is not None:
        if cash_debt >= 1:
            debt_score += 5
        elif cash_debt >= 0.5:
            debt_score += 3
    debt_score = min(25.0, debt_score)

    moat_score = 25.0 if moat_tag and moat_tag != "none" else 15.0
    moat_score += 15.0 if moat_tag == "wide" else (7.0 if moat_tag == "narrow" else 0.0)
    if op_margin is not None:
        om = op_margin / 100.0
        moat_score += 12 if om >= 0.25 else 8 if om >= 0.15 else 3 if om >= 0.08 else 0
    if gross_margin is not None:
        gm = gross_margin / 100.0
        moat_score += 10 if gm >= 0.55 else 7 if gm >= 0.40 else 3 if gm >= 0.25 else 0
    if roic is not None:
        rc = roic / 100.0
        moat_score += 10 if rc >= 0.18 else 7 if rc >= 0.12 else 3 if rc >= 0.08 else 0
    moat_score = max(0.0, min(100.0, moat_score))

    valuation_score = 0.0
    if fcf_yield is not None:
        valuation_score += min(12.0, max(0.0, fcf_yield) / 0.12 * 12)
    if pe is not None and pe > 0:
        valuation_score += 4 if pe <= 10 else 3 if pe <= 15 else 1 if pe <= 25 else 0
    if ev_to_ebitda is not None and ev_to_ebitda > 0:
        valuation_score += 4 if ev_to_ebitda <= 8 else 3 if ev_to_ebitda <= 12 else 1 if ev_to_ebitda <= 18 else 0
    valuation_score = min(20.0, valuation_score)

    missing = [k for k in ("market_cap", "fcf", "total_debt", "equity") if raw.get(k) is None]
    final_score = cash_score + debt_score + moat_score * 0.25 + valuation_score
    if missing:
        final_score -= min(12, len(missing) * 3)
    final_score = max(0.0, min(100.0, final_score))
    band = "A" if final_score >= 75 else "B" if final_score >= 60 else "C" if final_score >= 45 else "D"
    return {"codex_score": round(final_score, 1), "codex_band": band}


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

    if market in ("JP", "ALL"):
        tickers = config.all_jp()
        if limit:
            tickers = tickers[:limit]
        for t in tickers:
            raw = data.fetch_jp(t, use_cache=use_cache)
            if raw.get("error"):
                continue
            rows.append(build_row(raw))

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return df.sort_values("dhandho_score", ascending=False).reset_index(drop=True)


def diagnose(tickers, use_cache: bool = True) -> pd.DataFrame:
    """
    포트폴리오 건강검진: 사용자가 보유한 종목들을 Dhandho 4축으로 *객관 진단*한다.
    ⚠️ 매수/매도/보유 권유가 아니라 정보 제공용 점수표다 (data.fetch_auto 자동 감지).
    각 행에 data_ok(데이터 수집 성공 여부) 플래그 포함.
    """
    rows = []
    for raw_t in tickers:
        t = str(raw_t).strip()
        if not t:
            continue
        raw = data.fetch_auto(t, use_cache=use_cache)
        row = build_row(raw)
        row["input"] = t
        row["data_ok"] = not raw.get("error") and raw.get("market_cap") is not None
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("dhandho_score", ascending=False).reset_index(drop=True)


def diagnose_published(tickers, published_rows, use_cache: bool = True) -> pd.DataFrame:
    """
    published(배포) 모드 건강검진: 라이브 조회 없이 퍼블리시된 데이터에서 종목을 찾아 진단.
    공개 유니버스(S&P500+한국+일본)에 없는 종목은 data_ok=False.
    """
    idx = {str(r.get("ticker")): r for r in published_rows}
    rows = []
    for raw_t in tickers:
        t = str(raw_t).strip()
        if not t:
            continue
        key = t.upper()
        rec = (idx.get(t) or idx.get(key)
               or idx.get(t.split(".")[0]) or idx.get(key.split(".")[0]))
        if rec is None:
            row = build_row({"ticker": t, "market": "?", "name": t})
            row["data_ok"] = False
        else:
            row = build_row(rec)
            row["data_ok"] = True
        row["input"] = t
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("dhandho_score", ascending=False).reset_index(drop=True)


def strength_label(score) -> str:
    """Dhandho 점수 → 설명 라벨(행동 권유 아님, 점수 구간 설명)."""
    if score is None or (isinstance(score, float) and pd.isna(score)):
        return "데이터없음"
    if score >= 75:
        return "Dhandho 기준 강함"
    if score >= 50:
        return "보통"
    return "Dhandho 기준 약함"


# 화면/스냅샷용 컬럼 순서
DISPLAY_COLS = [
    "market", "ticker", "name", "moat_tag", "dhandho_score",
    "codex_score", "codex_band",
    "fcf_yield", "p_fcf", "debt_equity", "netdebt_ebitda",
    "roic", "gross_margin", "op_margin_std",
    "pe", "pb", "earnings_yield",
    "score_cashflow", "score_debt", "score_moat", "score_value",
    "downside_score", "passes", "flags",
]
