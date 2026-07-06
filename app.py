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
import i18n
import paid_gate
import portfolio_io
import screening
import tier_display
import waitlist

st.set_page_config(page_title="Dhandho Value Screener", page_icon="🏰", layout="wide")

i18n.set_lang(st.session_state.get("lang_select", "ko"))  # 위젯 라벨 자체가 한 텀 지연되지 않도록 먼저 동기화
_lang_choice = st.sidebar.selectbox(
    "🌐 Language / 언어 / 言語",  # 언어 중립적 라벨 — 방문자가 자기 언어를 못 읽어도 알아볼 수 있게 항상 3개국어 병기
    options=list(i18n.LANGS.keys()),
    format_func=lambda c: i18n.LANGS[c],
    index=list(i18n.LANGS.keys()).index(i18n.lang()),
    key="lang_select",
)
i18n.set_lang(_lang_choice)

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
st.sidebar.title(i18n.t("sidebar_title"))

market = st.sidebar.radio(i18n.t("market_label"), ["ALL", "US", "KR", "JP"], horizontal=True,
                          format_func=lambda m: i18n.t(f"market_{m}"))

if USE_PUBLISHED:
    us_limit = 0  # 미사용 (데이터는 published 파일에서 옴)
    _pub_meta = load_published()
    st.sidebar.success(i18n.t("deploy_badge", date=_pub_meta.get('generated_at', '?')))
else:
    us_limit = st.sidebar.slider(i18n.t("scan_limit_label"), 0, len(config.US_UNIVERSE),
                                 min(20, len(config.US_UNIVERSE)),
                                 help=i18n.t("scan_limit_help"))
    if st.sidebar.button(i18n.t("refresh_button")):
        st.cache_data.clear()
        import data as _d
        _d.clear_cache()
        st.rerun()

# ──────────────────────────────────────────────────────────────────────────
# 무료/유료 티어
# ──────────────────────────────────────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.markdown(f"**{i18n.t('paid_tier_header')}**")


@st.cache_data(ttl=300, show_spinner=False)
def _check_paid_email(email: str) -> bool:
    """Brevo 유료 리스트 조회 (Stripe 결제 웹훅이 자동으로 채움). 5분 캐시."""
    return paid_gate.is_paid_email(email)


_paid_email = st.sidebar.text_input(
    i18n.t("paid_email_label"), help=i18n.t("paid_email_help"))
_paid_code = st.sidebar.text_input(
    i18n.t("paid_code_label"), type="password", help=i18n.t("paid_code_help"))

_email_ok = bool(_paid_email) and _check_paid_email(_paid_email)
_code_ok = bool(_paid_code) and _paid_code.strip() in config.paid_access_codes()
IS_PAID = _email_ok or _code_ok

if IS_PAID:
    st.sidebar.success(i18n.t("paid_unlocked"))
elif _paid_email:
    st.sidebar.error(i18n.t("paid_email_fail"))
elif _paid_code:
    st.sidebar.error(i18n.t("paid_code_fail"))
else:
    st.sidebar.caption(i18n.free_preview_caption())

st.sidebar.markdown("---")
st.sidebar.markdown(f"**{i18n.t('threshold_header')}**")
TH = config.THRESHOLDS
fcf_min = st.sidebar.slider(i18n.t("th_fcf"), 0.0, 20.0, float(TH["fcf_yield_min"]), 0.5)
de_max = st.sidebar.slider(i18n.t("th_de"), 0.0, 3.0, float(TH["debt_equity_max"]), 0.1)
roic_min = st.sidebar.slider(i18n.t("th_roic"), 0.0, 40.0, float(TH["roic_min"]), 1.0)
pe_max = st.sidebar.slider(i18n.t("th_pe"), 5.0, 50.0, float(TH["pe_max"]), 1.0)
ey_min = st.sidebar.slider(i18n.t("th_ey"), 0.0, 20.0, float(TH["earnings_yield_min"]), 0.5)

# 슬라이더 값을 런타임 임계값에 반영 (점수/플래그 재계산 위해 빌드 전 주입)
TH["fcf_yield_min"] = fcf_min
TH["debt_equity_max"] = de_max
TH["roic_min"] = roic_min
TH["pe_max"] = pe_max
TH["earnings_yield_min"] = ey_min

st.sidebar.markdown("---")
st.sidebar.caption(i18n.t("live_caption"))

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
    st.error(i18n.t("no_data_error") + ("" if USE_PUBLISHED else i18n.t("no_data_hint")))
    st.stop()

# 원시 행을 현재 슬라이더 임계값으로 다시 스코어링 (네트워크 호출 없음 — 순수 계산)
df = pd.DataFrame([screening.build_row(row) for row in df_raw.to_dict("records")])
df = df.sort_values("dhandho_score", ascending=False).reset_index(drop=True)

# ──────────────────────────────────────────────────────────────────────────
# 헤더 & KPI
# ──────────────────────────────────────────────────────────────────────────
st.title(i18n.t("app_title"))
_src = (i18n.t("src_published", date=load_published().get('generated_at', '?'))
        if USE_PUBLISHED else i18n.t("src_live"))
st.caption(i18n.t("app_caption", n=len(df), src=_src))

passes = df[df["passes"]]
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric(i18n.t("kpi_pass"), i18n.t("unit_count", n=len(passes)), i18n.t("kpi_pass_delta", n=len(df)))
c2.metric(i18n.t("kpi_avg_score"), fmt(df["dhandho_score"].mean()))
c3.metric(i18n.t("kpi_avg_fcf"), fmt(df["fcf_yield"].dropna().mean(), "%"))
c4.metric(i18n.t("kpi_avg_de"), fmt(df["debt_equity"].dropna().mean(), digits=2))
c5.metric(i18n.t("kpi_wide_moat"), i18n.t("unit_count", n=(df['moat_tag'] == 'wide').sum()))

if not len(passes):
    st.info(i18n.t("no_pass_info"))
elif IS_PAID:
    top = passes.iloc[0]
    st.success(i18n.t(
        "top_candidate_paid", name=top['name'], ticker=top['ticker'],
        score=top['dhandho_score'], fcf=fmt(top['fcf_yield'], '%'),
        roic=fmt(top['roic'], '%'), pe=fmt(top['pe']), moat=top['moat_tag'],
    ))
else:
    preview = tier_display.free_preview_list(passes.to_dict("records"))
    if preview:
        top = preview[0]
        st.success(i18n.t(
            "top_candidate_free", rank=i18n.rank_label(), name=top['name'], ticker=top['ticker'],
            score=top['dhandho_score'], fcf=fmt(top['fcf_yield'], '%'),
            roic=fmt(top['roic'], '%'), pe=fmt(top['pe']), moat=top['moat_tag'],
        ))
        st.caption(i18n.t("top_candidate_free_note", skip=config.FREE_TIER_SKIP))
    else:
        st.info(i18n.t("no_preview_info", rank=i18n.rank_label()))

# ──────────────────────────────────────────────────────────────────────────
# 구독 신청 (무료 뉴스레터 / 유료판 얼리버드 대기)
# ──────────────────────────────────────────────────────────────────────────
_MSG_KEY = {
    "invalid_email": "msg_invalid_email", "not_configured": "msg_not_configured",
    "error": "msg_error", "success_free": "msg_success_free", "success_waitlist": "msg_success_waitlist",
}

with st.container(border=True):
    sg1, sg2 = st.columns([2.2, 1])
    with sg1:
        st.markdown(f"#### {i18n.t('signup_header')}")
        st.markdown(i18n.t("signup_body", rank=i18n.rank_label()))
    with sg2:
        with st.form("signup_form", clear_on_submit=True):
            sg_intent = st.radio(
                "signup_intent", ["free", "waitlist"],
                format_func=lambda v: i18n.t("signup_free_option" if v == "free" else "signup_waitlist_option"),
                label_visibility="collapsed")
            sg_email = st.text_input(
                "email", placeholder=i18n.t("signup_email_placeholder"), label_visibility="collapsed")
            sg_submit = st.form_submit_button(i18n.t("signup_submit_button"), width="stretch")
        if sg_submit:
            join_fn = waitlist.join_free if sg_intent == "free" else waitlist.join_waitlist
            ok, code = join_fn(sg_email)
            (st.success if ok else st.error)(i18n.t(_MSG_KEY[code]))

# ──────────────────────────────────────────────────────────────────────────
# 섹션 1: 스크리닝 결과 (+ 종목 클릭 시 인라인 상세)
# ──────────────────────────────────────────────────────────────────────────
st.divider()
st.header(i18n.t("tab1"))
only_pass = st.checkbox(i18n.t("only_pass_checkbox"), value=False, disabled=not IS_PAID)
if not IS_PAID:
    st.caption(i18n.t("free_preview_notice", rank=i18n.rank_label()))
pass_df = df[df["passes"]].sort_values("dhandho_score", ascending=False)
full_df = pass_df if only_pass else df.sort_values("dhandho_score", ascending=False)

hidden_count = 0
if IS_PAID:
    view_df = full_df
else:
    preview_idx = pass_df.index[
        config.FREE_TIER_SKIP : config.FREE_TIER_SKIP + config.FREE_TIER_LIMIT
    ]
    view_df = pass_df.loc[preview_idx]
    hidden_count = tier_display.free_hidden_pass_count(len(pass_df))
view_df = view_df.reset_index(drop=True)  # 아래 행 선택 인덱스가 view_df 위치와 정확히 대응하도록

cols = ["market", "ticker", "name", "moat_tag", "dhandho_score",
        "codex_score", "codex_band",
        "fcf_yield", "p_fcf", "debt_equity", "netdebt_ebitda",
        "roic", "gross_margin", "pe", "pb", "earnings_yield",
        "downside_score", "passes"]
show = view_df[cols].copy()
col_labels = [i18n.t(k) for k in (
    "col_market", "col_ticker", "col_name", "col_moat", "col_dhandho",
    "col_ai_score", "col_ai_band", "col_fcf", "col_pfcf", "col_de", "col_ndebitda",
    "col_roic", "col_gm", "col_pe", "col_pb", "col_ey", "col_downside", "col_passes",
)]
show.columns = col_labels
C = dict(zip(
    ("market", "ticker", "name", "moat", "dhandho", "ai_score", "ai_band", "fcf", "pfcf",
     "de", "ndebitda", "roic", "gm", "pe", "pb", "ey", "downside", "passes"),
    col_labels,
))
show.insert(3, i18n.t("col_detail"), "🔎")  # 종목명 우측 — 클릭 가능함을 알리는 시각적 단서

# 반투명 오버레이 색상 사용 — 라이트/다크 테마 어느 배경 위에서도 자연스럽게 얹힌다.
def hl_pass(v):
    return "background-color:rgba(46,204,113,0.28);font-weight:bold" if v else ""

def hl_score(v):
    if pd.isna(v):
        return ""
    if v >= 75:
        return "background-color:rgba(46,204,113,0.28)"
    if v >= 50:
        return "background-color:rgba(241,196,15,0.28)"
    return ""

def hl_moat(v):
    return {"wide": "background-color:rgba(52,152,219,0.30)",
            "narrow": "background-color:rgba(52,152,219,0.15)"}.get(v, "")

fmt_map = {
    C["dhandho"]: "{:.1f}", C["ai_score"]: "{:.1f}",
    C["fcf"]: "{:.1f}", C["pfcf"]: "{:.1f}",
    C["de"]: "{:.2f}", C["ndebitda"]: "{:.1f}", C["roic"]: "{:.1f}",
    C["gm"]: "{:.1f}", C["pe"]: "{:.1f}", C["pb"]: "{:.1f}",
    C["ey"]: "{:.1f}", C["downside"]: "{:.0f}",
}
sty = (show.style.format(fmt_map, na_rep="—")
       .map(hl_pass, subset=[C["passes"]])
       .map(hl_score, subset=[C["dhandho"]])
       .map(hl_moat, subset=[C["moat"]]))
table_event = st.dataframe(
    sty, width="stretch", hide_index=True, height=560,
    on_select="rerun", selection_mode="single-row", key="screening_table",
)
st.caption(i18n.t("detail_hint"))
st.caption(i18n.t("table_legend"))

if not IS_PAID:
    st.info(
        f"🔒 {i18n.free_preview_caption()} "
        + (i18n.t("lock_hidden", n=hidden_count) if hidden_count else i18n.t("lock_generic"))
    )

if IS_PAID:
    st.download_button(
        i18n.t("csv_button"),
        data=full_df[cols].to_csv(index=False).encode("utf-8-sig"),
        file_name=f"dhandho_screening_{dt.date.today().isoformat()}.csv",
        mime="text/csv",
    )

# 종목 클릭 시 인라인 상세(레이더 차트 등) — view_df 는 이미 무료/유료 티어로 걸러진 상태라
# 자유 티어에서도 미리보기 구간(6~10위)에 대해서만 상세를 볼 수 있다.
selected_rows = (table_event.selection.rows if table_event and table_event.selection else [])
if selected_rows and selected_rows[0] < len(view_df):
    row = view_df.iloc[selected_rows[0]]
    with st.container(border=True):
        rc1, rc2 = st.columns([1, 1])
        with rc1:
            radar = go.Figure(go.Scatterpolar(
                r=[row["score_cashflow"], row["score_debt"], row["score_moat"], row["score_value"],
                   row["score_cashflow"]],
                theta=[i18n.t("radar_axis1"), i18n.t("radar_axis2"), i18n.t("radar_axis3"),
                       i18n.t("radar_axis4"), i18n.t("radar_axis1")],
                fill="toself", line_color="#2980b9"))
            radar.update_layout(height=380, margin=dict(t=40, b=20),
                                polar=dict(radialaxis=dict(range=[0, 100])),
                                title=i18n.t("radar_title", name=row['name']))
            st.plotly_chart(radar, width="stretch")
        with rc2:
            st.markdown(f"### {row['name']} ({row['ticker']})")
            st.markdown(i18n.t("detail_summary", score=row['dhandho_score'],
                               downside=fmt(row['downside_score'], digits=0), moat=row['moat_tag']))
            st.caption(i18n.t("detail_ai", score=fmt(row.get('codex_score')), band=row.get('codex_band', '—')))
            st.markdown(i18n.t("detail_axis1", fcf=fmt(row['fcf_yield'], '%'), pfcf=fmt(row['p_fcf'])))
            st.markdown(i18n.t("detail_axis2", de=fmt(row['debt_equity'], digits=2), nde=fmt(row['netdebt_ebitda'])))
            st.markdown(i18n.t("detail_axis3", roic=fmt(row['roic'], '%'), gm=fmt(row['gross_margin'], '%'),
                               std=fmt(row['op_margin_std'])))
            st.markdown(i18n.t("detail_axis4", pe=fmt(row['pe']), pb=fmt(row['pb']), ey=fmt(row['earnings_yield'], '%')))
            flags = " ".join(i18n.translate_flag(f) for f in row['flags']) if row['flags'] else i18n.t("detail_flags_none")
            st.markdown(i18n.t("detail_flags", flags=flags))
            if row["market"] == "KR" and row.get("source"):
                st.caption(i18n.t("detail_kr_source", as_of=row.get('as_of'), source=row.get('source')))

# ──────────────────────────────────────────────────────────────────────────
# 섹션 2: 신규/탈락 (주간 스냅샷)
# ──────────────────────────────────────────────────────────────────────────
st.divider()
st.header(i18n.t("tab4"))
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

# ──────────────────────────────────────────────────────────────────────────
# 섹션 3: 포트폴리오 건강검진 (진단형 — 매수/매도 권유 아님)
# ──────────────────────────────────────────────────────────────────────────
st.divider()
st.header(i18n.t("tab5"))
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
st.caption(i18n.t("footer_disclaimer"))
