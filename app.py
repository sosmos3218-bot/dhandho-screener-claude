# -*- coding: utf-8 -*-
"""
단도(Dhandho) 가치투자 스크리닝 대시보드
========================================
모니시 파브라이의 Dhandho 철학으로 저평가·강현금흐름·저부채·해자 기업 발굴.
실행:  .venv/bin/streamlit run app.py   (또는 ./run.sh)
"""
import datetime as dt
import glob
import json
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
import portfolio_io
import screening

st.set_page_config(page_title="Dhandho 가치투자 스크리너", page_icon="🏰", layout="wide")

SNAP_DIR = os.path.join(os.path.dirname(__file__), "snapshots")
PUBLISHED_FILE = os.path.join(os.path.dirname(__file__), "published", "screening_data.json")

# 배포(클라우드) 모드: 로컬이 내보낸 published/screening_data.json 만 읽어 렌더한다.
#   클라우드에서 yfinance/pykrx 를 호출하지 않음 → 레이트리밋·한국차단·속도 문제 회피.
#   활성화: 환경변수 DHANDHO_MODE=published  (Streamlit Cloud → App settings → Secrets/Env)
USE_PUBLISHED = os.environ.get("DHANDHO_MODE", "").lower() == "published"


# ──────────────────────────────────────────────────────────────────────────
# 데이터 로딩 (캐시)
# ──────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=43200, show_spinner="📡 시세·재무 수집 중 (yfinance/pykrx)...")
def load_universe(market: str, limit: int) -> pd.DataFrame:
    return screening.build_universe(market, use_cache=True, limit=limit or None)


@st.cache_data(ttl=3600)
def load_published() -> dict:
    with open(PUBLISHED_FILE, encoding="utf-8") as f:
        return json.load(f)


def fmt(v, suffix="", digits=1):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{v:,.{digits}f}{suffix}"


def load_latest_snapshots():
    """최신 2개 스냅샷(JSON) 로드 → (latest_dict, prev_dict) 또는 (None, None)."""
    files = sorted(glob.glob(os.path.join(SNAP_DIR, "dhandho_*.json")))
    if not files:
        return None, None
    latest = json.load(open(files[-1], encoding="utf-8"))
    prev = json.load(open(files[-2], encoding="utf-8")) if len(files) >= 2 else None
    return latest, prev


# ──────────────────────────────────────────────────────────────────────────
# 사이드바
# ──────────────────────────────────────────────────────────────────────────
st.sidebar.title("⚙️ Dhandho 필터")

market = st.sidebar.radio("시장", ["ALL", "US", "KR", "JP"], horizontal=True,
                          format_func=lambda m: {"ALL": "전체", "US": "미국", "KR": "한국", "JP": "일본"}[m])

if USE_PUBLISHED:
    us_limit = 0  # 미사용 (데이터는 published 파일에서 옴)
    _pub_meta = load_published()
    st.sidebar.success(
        f"📦 **배포 모드** · 데이터 기준\n\n**{_pub_meta.get('generated_at', '?')}**\n\n"
        "로컬에서 분석한 결과를 읽어 표시합니다. (클라우드에서 실시간 수집 안 함)")
else:
    us_limit = st.sidebar.slider("스캔 종목 수 (미국·일본, 0=전체)", 0, len(config.US_UNIVERSE),
                                 min(20, len(config.US_UNIVERSE)),
                                 help="yfinance 레이트리밋 방어용. 미국·일본 유니버스에 적용.")
    if st.sidebar.button("🔄 새로고침 (캐시 비우기)"):
        st.cache_data.clear()
        import data as _d
        _d.clear_cache()
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("**핵심 임계값** (config.py 기본)")
TH = config.THRESHOLDS
fcf_min = st.sidebar.slider("① FCF Yield ≥ (%)", 0.0, 20.0, float(TH["fcf_yield_min"]), 0.5)
de_max = st.sidebar.slider("② 부채/자본 ≤", 0.0, 3.0, float(TH["debt_equity_max"]), 0.1)
roic_min = st.sidebar.slider("③ ROIC ≥ (%)", 0.0, 40.0, float(TH["roic_min"]), 1.0)
pe_max = st.sidebar.slider("④ P/E ≤", 5.0, 50.0, float(TH["pe_max"]), 1.0)
ey_min = st.sidebar.slider("④ Earnings Yield ≥ (%)", 0.0, 20.0, float(TH["earnings_yield_min"]), 0.5)

# 슬라이더 값을 런타임 임계값에 반영 (점수/플래그 재계산 위해 빌드 전 주입)
TH["fcf_yield_min"] = fcf_min
TH["debt_equity_max"] = de_max
TH["roic_min"] = roic_min
TH["pe_max"] = pe_max
TH["earnings_yield_min"] = ey_min

st.sidebar.markdown("---")
st.sidebar.caption(
    "🟢 LIVE: 펀더멘털=yfinance(미국 S&P500 + 한국 .KS/.KQ — 시총·FCF·부채·ROIC·순이익 자동), "
    "한국 가격=pykrx\n\n"
    "🟡 수동(config.py): 해자(Moat) 정성 태그 + yfinance 결측 시 폴백값. "
    "금융주는 모델 특성상 과소평가될 수 있음."
)

# ──────────────────────────────────────────────────────────────────────────
# 데이터 로드 + 슬라이더 임계값으로 재스코어링
# ──────────────────────────────────────────────────────────────────────────
if USE_PUBLISHED:
    _pub = load_published()
    published_rows = _pub["rows"]              # 건강검진 lookup 에도 사용
    rows = published_rows if market == "ALL" else [r for r in published_rows if r.get("market") == market]
    df_raw = pd.DataFrame(rows)
else:
    published_rows = None
    df_raw = load_universe(market, us_limit)

if df_raw.empty:
    st.error("표시할 데이터가 없습니다." +
             ("" if USE_PUBLISHED else " 사이드바에서 시장/종목 수를 조정하거나 새로고침하세요."))
    st.stop()

# 원시 행을 현재 슬라이더 임계값으로 다시 스코어링 (네트워크 호출 없음 — 순수 계산)
df = pd.DataFrame([screening.build_row(row) for row in df_raw.to_dict("records")])
df = df.sort_values("dhandho_score", ascending=False).reset_index(drop=True)

# ──────────────────────────────────────────────────────────────────────────
# 헤더 & KPI
# ──────────────────────────────────────────────────────────────────────────
st.title("🏰 Dhandho 가치투자 스크리너")
_src = (f"📦 배포 데이터 기준 {load_published().get('generated_at','?')} (로컬 분석본)"
        if USE_PUBLISHED else "펀더멘털=yfinance LIVE / 한국 가격=pykrx")
st.caption(
    f"모니시 파브라이 『단도(Dhandho)』 — \"Heads I win, tails I don't lose much\" · "
    f"종목 {len(df)}개 · {_src}"
)

passes = df[df["passes"]]
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("✅ 조건 통과", f"{len(passes)}개", f"전체 {len(df)}개 중")
c2.metric("평균 Dhandho 점수", fmt(df["dhandho_score"].mean()))
c3.metric("평균 FCF Yield", fmt(df["fcf_yield"].dropna().mean(), "%"))
c4.metric("평균 부채/자본", fmt(df["debt_equity"].dropna().mean(), digits=2))
c5.metric("와이드 해자 종목", f"{(df['moat_tag'] == 'wide').sum()}개")

if len(passes):
    top = passes.iloc[0]
    st.success(
        f"🏆 최우선 후보: **{top['name']}** ({top['ticker']}) · "
        f"Dhandho {top['dhandho_score']} · FCF Yield {fmt(top['fcf_yield'],'%')} · "
        f"ROIC {fmt(top['roic'],'%')} · P/E {fmt(top['pe'])} · 해자 {top['moat_tag']}"
    )
else:
    st.info("현재 임계값을 모두 통과하는 종목이 없습니다. 시장이 비싸거나 필터가 엄격합니다 — 사이드바에서 완화해 보세요.")

# ──────────────────────────────────────────────────────────────────────────
# 탭 구성
# ──────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📋 스크리닝 결과", "📊 분석 차트", "🔬 종목 상세",
     "🔄 신규/탈락(주간 스냅샷)", "🩺 포트폴리오 건강검진"])

# ── 탭 1: 결과 테이블 ──────────────────────────────────────────────────────
with tab1:
    only_pass = st.checkbox("조건 통과 종목만 보기", value=False)
    view_df = df[df["passes"]] if only_pass else df

    cols = ["market", "ticker", "name", "moat_tag", "dhandho_score",
            "fcf_yield", "p_fcf", "debt_equity", "netdebt_ebitda",
            "roic", "gross_margin", "pe", "pb", "earnings_yield",
            "downside_score", "passes"]
    show = view_df[cols].copy()
    show.columns = ["시장", "코드", "종목", "해자", "Dhandho점수",
                    "FCF수익률%", "P/FCF", "부채/자본", "순부채/EBITDA",
                    "ROIC%", "매출총이익%", "P/E", "P/B", "이익수익률%",
                    "하방방어", "통과"]

    def hl_pass(v):
        return "background-color:#d5f5e3;font-weight:bold" if v else ""

    def hl_score(v):
        if pd.isna(v):
            return ""
        if v >= 75:
            return "background-color:#d5f5e3"
        if v >= 50:
            return "background-color:#fcf3cf"
        return ""

    def hl_moat(v):
        return {"wide": "background-color:#d6eaf8", "narrow": "background-color:#ebf5fb"}.get(v, "")

    fmt_map = {
        "Dhandho점수": "{:.1f}", "FCF수익률%": "{:.1f}", "P/FCF": "{:.1f}",
        "부채/자본": "{:.2f}", "순부채/EBITDA": "{:.1f}", "ROIC%": "{:.1f}",
        "매출총이익%": "{:.1f}", "P/E": "{:.1f}", "P/B": "{:.1f}",
        "이익수익률%": "{:.1f}", "하방방어": "{:.0f}",
    }
    sty = (show.style.format(fmt_map, na_rep="—")
           .map(hl_pass, subset=["통과"])
           .map(hl_score, subset=["Dhandho점수"])
           .map(hl_moat, subset=["해자"]))
    st.dataframe(sty, width="stretch", hide_index=True, height=560)
    st.caption(
        "🟩 통과 · Dhandho점수 75↑ 진녹/50↑ 노랑 · 🟦 해자(wide/narrow) · "
        "기본 통과 규칙: 4개 축 중 3개 이상 충족 + **부채 축 필수**."
    )

# ── 탭 2: 분석 차트 ────────────────────────────────────────────────────────
with tab2:
    plot_df = df[df["fcf_yield"].notna() & df["dhandho_score"].notna()].copy()
    if not plot_df.empty:
        plot_df["size"] = plot_df["market_cap"].fillna(plot_df["market_cap"].median()).clip(lower=1)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=plot_df["fcf_yield"], y=plot_df["dhandho_score"],
            mode="markers+text", text=plot_df["ticker"], textposition="top center",
            textfont=dict(size=9),
            marker=dict(
                size=(plot_df["size"] ** 0.18) * 4,
                color=plot_df["debt_equity"].fillna(0).clip(0, 3),
                colorscale="RdYlGn_r", showscale=True,
                colorbar=dict(title="부채/자본"), line=dict(width=0.5, color="#333"),
            ),
            customdata=plot_df[["name", "roic", "pe"]],
            hovertemplate="<b>%{customdata[0]}</b><br>FCF수익률 %{x:.1f}%<br>"
                          "Dhandho %{y:.1f}<br>ROIC %{customdata[1]:.1f}%<br>"
                          "P/E %{customdata[2]:.1f}<extra></extra>",
        ))
        fig.add_vline(x=config.THRESHOLDS["fcf_yield_min"], line_dash="dash",
                      line_color="green", annotation_text=f"FCF≥{config.THRESHOLDS['fcf_yield_min']:.0f}%")
        fig.update_layout(
            height=480, margin=dict(t=30, b=10),
            xaxis_title="FCF Yield (시총 대비 잉여현금흐름, %)  →  오른쪽일수록 쌈",
            yaxis_title="Dhandho 종합 점수",
            title="버블 크기=시가총액 · 색=부채/자본(녹=낮음, 적=높음)")
        st.plotly_chart(fig, width="stretch")

    st.markdown("#### 상위 종목 Dhandho 점수")
    topn = df.head(15)
    colors = ["#27ae60" if p else "#95a5a6" for p in topn["passes"]]
    fig2 = go.Figure(go.Bar(
        x=topn["dhandho_score"], y=topn["ticker"] + " " + topn["name"].str.slice(0, 12),
        orientation="h", marker_color=colors,
        text=[f"{v:.0f}" for v in topn["dhandho_score"]], textposition="outside"))
    fig2.update_layout(height=max(320, 32 * len(topn)), margin=dict(t=10, b=10),
                       yaxis=dict(autorange="reversed"), xaxis_title="Dhandho 점수 (녹색=통과)")
    st.plotly_chart(fig2, width="stretch")

# ── 탭 3: 종목 상세 (레이더) ──────────────────────────────────────────────
with tab3:
    names = (df["ticker"] + " · " + df["name"]).tolist()
    sel = st.selectbox("종목 선택", names, index=0)
    row = df.iloc[names.index(sel)]
    cc1, cc2 = st.columns([1, 1])
    with cc1:
        radar = go.Figure(go.Scatterpolar(
            r=[row["score_cashflow"], row["score_debt"], row["score_moat"], row["score_value"],
               row["score_cashflow"]],
            theta=["현금흐름①", "저부채②", "해자③", "저평가④", "현금흐름①"],
            fill="toself", line_color="#2980b9"))
        radar.update_layout(height=380, margin=dict(t=40, b=20),
                            polar=dict(radialaxis=dict(range=[0, 100])),
                            title=f"{row['name']} — 4축 점수")
        st.plotly_chart(radar, width="stretch")
    with cc2:
        st.markdown(f"### {row['name']} ({row['ticker']})")
        st.markdown(f"**Dhandho 종합 {row['dhandho_score']}** · 하방방어 {fmt(row['downside_score'],digits=0)} · 해자 `{row['moat_tag']}`")
        st.markdown(f"- ① FCF Yield **{fmt(row['fcf_yield'],'%')}** · P/FCF {fmt(row['p_fcf'])}")
        st.markdown(f"- ② 부채/자본 **{fmt(row['debt_equity'],digits=2)}** · 순부채/EBITDA {fmt(row['netdebt_ebitda'])}")
        st.markdown(f"- ③ ROIC **{fmt(row['roic'],'%')}** · 매출총이익률 {fmt(row['gross_margin'],'%')} · 영업이익률 안정성(σ) {fmt(row['op_margin_std'])}")
        st.markdown(f"- ④ P/E **{fmt(row['pe'])}** · P/B {fmt(row['pb'])} · 이익수익률 {fmt(row['earnings_yield'],'%')}")
        st.markdown(f"- 충족 조건: {' '.join(row['flags']) if row['flags'] else '없음'}")
        if row["market"] == "KR" and row.get("source"):
            st.caption(f"🟡 한국 펀더멘털 INPUT — as_of {row.get('as_of')} · {row.get('source')}")

# ── 탭 4: 주간 스냅샷 diff ────────────────────────────────────────────────
with tab4:
    st.markdown("#### 주간 cron 스냅샷 기반 신규 진입 / 탈락 종목")
    st.caption("`python snapshot.py` (또는 주간 스케줄)가 통과 종목을 snapshots/ 에 저장하고 직전과 비교합니다.")
    latest, prev = load_latest_snapshots()
    if latest is None:
        st.info("아직 스냅샷이 없습니다. 터미널에서 `python snapshot.py` 를 실행하거나 주간 스케줄을 등록하세요.")
    else:
        latest_set = {r["ticker"]: r for r in latest["passes"]}
        prev_set = {r["ticker"]: r for r in (prev["passes"] if prev else [])}
        new = [latest_set[t] for t in latest_set if t not in prev_set]
        dropped = [prev_set[t] for t in prev_set if t not in latest_set]
        cA, cB = st.columns(2)
        with cA:
            st.markdown(f"**🆕 신규 진입 ({len(new)})** · 스냅샷 {latest['date']}")
            if new:
                st.table(pd.DataFrame([{"코드": r["ticker"], "종목": r["name"],
                                        "Dhandho": r["dhandho_score"]} for r in new]))
            else:
                st.write("없음")
        with cB:
            st.markdown(f"**❌ 탈락 ({len(dropped)})** · 직전 {prev['date'] if prev else '—'}")
            if dropped:
                st.table(pd.DataFrame([{"코드": r["ticker"], "종목": r["name"],
                                        "Dhandho": r["dhandho_score"]} for r in dropped]))
            else:
                st.write("없음")

# ── 탭 5: 포트폴리오 건강검진 (진단형 — 매수/매도 권유 아님) ────────────────
with tab5:
    st.markdown("#### 🩺 내 보유종목 Dhandho 건강검진")
    st.info(
        "ℹ️ **이 기능은 보유종목이 Dhandho 4축(현금흐름·부채·해자·저평가)에서 "
        "어떤 점수인지 보여주는 객관 지표 진단입니다.** "
        "특정 종목의 매수·매도·보유, '물타기' 또는 '손절' 여부를 권유하지 않습니다. "
        "점수의 해석과 모든 투자 판단은 전적으로 본인의 몫입니다.",
        icon="ℹ️")

    # 1) 입력 양식 받기
    st.markdown("**1) 입력 양식 받기** (선택) — 받아서 보유종목을 채운 뒤 업로드하세요")
    dc1, dc2, _ = st.columns([1.2, 1.2, 3])
    dc1.download_button("⬇️ 엑셀 템플릿(.xlsx)", data=portfolio_io.template_xlsx_bytes(),
                        file_name="dhandho_portfolio_template.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    dc2.download_button("⬇️ CSV 템플릿(.csv)", data=portfolio_io.template_csv_bytes(),
                        file_name="dhandho_portfolio_template.csv", mime="text/csv")

    # 2) 파일 업로드 또는 직접 입력
    st.markdown("**2) 보유종목 입력** — 파일 업로드(우선) 또는 아래 직접 입력")
    up = st.file_uploader("포트폴리오 파일 (.xlsx / .csv)", type=["xlsx", "csv"],
                          help="'티커' 열 필수. 보유수량·평균단가는 선택(평가손익 표시에 사용).")
    txt = st.text_area("또는 티커 직접 입력 (줄바꿈/콤마 구분)",
                       value="AAPL\n005930\n7203.T\n033780\nKO", height=110)
    st.caption("티커 형식: 미국=AAPL · 한국=005930 (6자리) · 일본=7203.T (.T)")
    if USE_PUBLISHED:
        st.caption("📦 배포 모드: 공개 유니버스(S&P500·한국·일본)에 포함된 종목만 진단됩니다 "
                   "(클라우드에서 실시간 조회 안 함).")
    go = st.button("🔍 건강검진 실행", type="primary")

    @st.cache_data(ttl=43200, show_spinner="보유종목 진단 중...")
    def run_diagnose(tickers_tuple):
        if USE_PUBLISHED:
            return screening.diagnose_published(list(tickers_tuple), published_rows)
        return screening.diagnose(list(tickers_tuple), use_cache=True)

    if go:
        raw_list, holdings = [], {}  # holdings: 티커 -> (수량, 평단)
        if up is not None:
            try:
                pdf = portfolio_io.parse_upload(up)
                raw_list = pdf["ticker"].tolist()
                holdings = {row["ticker"]: (row["qty"], row["avg_price"])
                            for _, row in pdf.iterrows()}
                st.caption(f"📄 업로드 파싱: {len(raw_list)}개 종목 (파일 우선 적용)")
            except Exception as e:
                st.error(f"파일 파싱 실패: {e}")
        else:
            raw_list = [t.strip() for chunk in txt.split("\n")
                        for t in chunk.split(",") if t.strip()]

        if not raw_list:
            st.warning("티커를 1개 이상 입력하거나 파일을 올려주세요.")
        else:
            d = run_diagnose(tuple(raw_list))
            ok = d[d["data_ok"]]
            bad = d[~d["data_ok"]]

            if not ok.empty:
                s1, s2, s3 = st.columns(3)
                s1.metric("진단 종목", f"{len(ok)}개")
                s2.metric("평균 Dhandho", fmt(ok["dhandho_score"].mean()))
                strong = int((ok["dhandho_score"] >= 75).sum())
                s3.metric("Dhandho 기준 강함(75↑)", f"{strong}개")

            # 종목별 진단 카드
            for _, r in ok.iterrows():
                label = screening.strength_label(r["dhandho_score"])
                badge = {"Dhandho 기준 강함": "🟢", "보통": "🟡", "Dhandho 기준 약함": "🔴"}.get(label, "⚪")
                with st.container(border=True):
                    h1, h2 = st.columns([2, 3])
                    with h1:
                        st.markdown(f"### {r['name']}")
                        st.caption(f"{r['input']} · {r['market']} · 해자 {r['moat_tag']}")
                        st.metric("Dhandho 종합", f"{r['dhandho_score']}", f"{badge} {label}")
                    with h2:
                        ax = pd.DataFrame({
                            "축": ["①현금흐름", "②저부채", "③해자", "④저평가"],
                            "점수": [r["score_cashflow"], r["score_debt"],
                                   r["score_moat"], r["score_value"]],
                        })
                        st.bar_chart(ax.set_index("축"), height=180, horizontal=True)
                    # 객관 지표 (사실 나열 — 해석/권유 없음)
                    st.markdown(
                        f"- ① FCF수익률 **{fmt(r['fcf_yield'],'%')}** · P/FCF {fmt(r['p_fcf'])}  "
                        f"&nbsp;②부채/자본 **{fmt(r['debt_equity'],digits=2)}** · 순부채/EBITDA {fmt(r['netdebt_ebitda'])}\n"
                        f"- ③ ROIC **{fmt(r['roic'],'%')}** · 매출총이익률 {fmt(r['gross_margin'],'%')}  "
                        f"&nbsp;④ P/E **{fmt(r['pe'])}** · P/B {fmt(r['pb'])} · 이익수익률 {fmt(r['earnings_yield'],'%')}"
                    )
                    # 업로드 파일에 보유수량/평단이 있으면 본인 포지션 사실 표시 (동일통화 가정)
                    if r["input"] in holdings:
                        q, avg = holdings[r["input"]]
                        parts = []
                        if pd.notna(q):
                            parts.append(f"보유 {q:,.0f}주")
                        if pd.notna(avg):
                            parts.append(f"평단 {avg:,.2f}")
                            if r.get("price"):
                                ret = (r["price"] - avg) / avg * 100
                                parts.append(f"현재 {r['price']:,.2f} · 평가손익 **{ret:+.1f}%**")
                        if parts:
                            st.caption("💼 " + " · ".join(parts) + "  (본인 입력 기준·동일통화 가정, 사실 정보)")
                    weak = [n for n, s in [("현금흐름", r["score_cashflow"]), ("부채", r["score_debt"]),
                                           ("해자", r["score_moat"]), ("저평가", r["score_value"])] if s < 40]
                    strongx = [n for n, s in [("현금흐름", r["score_cashflow"]), ("부채", r["score_debt"]),
                                              ("해자", r["score_moat"]), ("저평가", r["score_value"])] if s >= 70]
                    note = []
                    if strongx:
                        note.append(f"상대적 강점: {', '.join(strongx)}")
                    if weak:
                        note.append(f"상대적 약점: {', '.join(weak)}")
                    if note:
                        st.caption("📌 " + " · ".join(note) + "  (사실 정보이며 매매 판단 아님)")

            if not bad.empty:
                st.warning("조회 실패(티커/형식 확인): " +
                           ", ".join(bad["input"].astype(str).tolist()))

    st.caption("⚠️ 다시 강조: 본 진단은 **정보 제공·교육용 객관 점수**이며 매수·매도·보유 권유가 아닙니다. "
               "'물타기/손절' 판단을 대신하지 않습니다. 데이터는 yfinance(지연·오류 가능) 기준입니다.")

st.markdown("---")
st.caption(
    "⚠️ 본 대시보드는 정보 제공용이며 투자 권유가 아닙니다. 해자(Moat)는 본질적으로 정성 판단이며 "
    "여기서는 ROIC·마진 안정성·수동 태그로 근사한 보조 지표입니다. 펀더멘털은 yfinance(미국·한국·일본) "
    "자동 수집값으로 지연·오류가 있을 수 있으니, 실제 판단 전 DART·FnGuide·증권사 리포트로 반드시 검증하세요."
)
