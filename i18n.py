# -*- coding: utf-8 -*-
"""
다국어 문자열 (한국어/영어/일본어)
==================================
app.py 가 st.session_state['lang']로 언어를 전환한다. 이 모듈은 Streamlit 세션에
의존하므로 UI 전용이며, newsletter.py(발송용, 한국어 고정)와는 분리되어 있다.
"""
import streamlit as st

import config

LANGS = {"ko": "한국어", "en": "English", "ja": "日本語"}

_S = {
    # ── 사이드바 ──────────────────────────────────────────────────────────
    "sidebar_title": {"ko": "⚙️ Dhandho 필터", "en": "⚙️ Dhandho Filters", "ja": "⚙️ Dhandhoフィルター"},
    "market_label": {"ko": "시장", "en": "Market", "ja": "市場"},
    "market_ALL": {"ko": "전체", "en": "All", "ja": "全市場"},
    "market_US": {"ko": "미국", "en": "US", "ja": "米国"},
    "market_KR": {"ko": "한국", "en": "Korea", "ja": "韓国"},
    "market_JP": {"ko": "일본", "en": "Japan", "ja": "日本"},
    "deploy_badge": {
        "ko": "📦 **배포 모드** · 데이터 기준\n\n**{date}**",
        "en": "📦 **Published mode** · data as of\n\n**{date}**",
        "ja": "📦 **公開モード** · データ基準\n\n**{date}**",
    },
    "scan_limit_label": {
        "ko": "스캔 종목 수 (미국·일본, 0=전체)",
        "en": "Scan count (US/Japan, 0=all)",
        "ja": "スキャン銘柄数（米国・日本、0=全件）",
    },
    "scan_limit_help": {
        "ko": "yfinance 레이트리밋 방어용. 미국·일본 유니버스에 적용.",
        "en": "Protects against yfinance rate limits. Applies to the US/Japan universe.",
        "ja": "yfinanceのレート制限対策。米国・日本ユニバースに適用されます。",
    },
    "refresh_button": {"ko": "🔄 새로고침 (캐시 비우기)", "en": "🔄 Refresh (clear cache)", "ja": "🔄 更新（キャッシュ削除）"},
    "paid_tier_header": {"ko": "🔓 유료판", "en": "🔓 Paid tier", "ja": "🔓 有料版"},
    "paid_email_label": {"ko": "유료판 이메일", "en": "Paid tier email", "ja": "有料版メールアドレス"},
    "paid_email_help": {
        "ko": "결제에 사용한 이메일을 입력하면 자동으로 확인됩니다.",
        "en": "Enter the email you used to pay — it's verified automatically.",
        "ja": "決済に使用したメールアドレスを入力すると自動で確認されます。",
    },
    "paid_code_label": {"ko": "또는 백업 코드", "en": "Or backup code", "ja": "またはバックアップコード"},
    "paid_code_help": {
        "ko": "이메일 자동 확인이 안 될 때 쓰는 수동 백업 코드입니다.",
        "en": "A manual backup code for when email verification doesn't work.",
        "ja": "メール自動確認ができない場合に使う手動バックアップコードです。",
    },
    "paid_unlocked": {
        "ko": "✅ 유료판 잠금 해제됨 — 전체 종목 표시",
        "en": "✅ Paid tier unlocked — showing all stocks",
        "ja": "✅ 有料版のロック解除済み — 全銘柄表示",
    },
    "paid_email_fail": {
        "ko": "결제 확인이 안 됩니다. 결제 시 사용한 이메일인지 확인하거나 잠시 후 다시 시도하세요.",
        "en": "Couldn't verify payment. Check that this is the email you paid with, or try again shortly.",
        "ja": "決済確認ができません。決済時のメールアドレスか確認するか、しばらくしてから再度お試しください。",
    },
    "paid_code_fail": {"ko": "코드가 올바르지 않습니다.", "en": "That code isn't valid.", "ja": "コードが正しくありません。"},
    "threshold_header": {
        "ko": "핵심 임계값 (config.py 기본)",
        "en": "Key thresholds (config.py defaults)",
        "ja": "主要しきい値（config.pyの初期値）",
    },
    "th_fcf": {"ko": "① FCF Yield ≥ (%)", "en": "① FCF Yield ≥ (%)", "ja": "① FCF利回り ≥ (%)"},
    "th_de": {"ko": "② 부채/자본 ≤", "en": "② Debt/Equity ≤", "ja": "② 負債/資本 ≤"},
    "th_roic": {"ko": "③ ROIC ≥ (%)", "en": "③ ROIC ≥ (%)", "ja": "③ ROIC ≥ (%)"},
    "th_pe": {"ko": "④ P/E ≤", "en": "④ P/E ≤", "ja": "④ PER ≤"},
    "th_ey": {"ko": "④ Earnings Yield ≥ (%)", "en": "④ Earnings Yield ≥ (%)", "ja": "④ 益回り ≥ (%)"},
    "live_caption": {
        "ko": "🟢 LIVE: 펀더멘털=yfinance(미국 S&P500 + 한국 .KS/.KQ — 시총·FCF·부채·ROIC·순이익 자동), "
              "한국 가격=pykrx\n\n🟡 수동(config.py): 해자(Moat) 정성 태그 + yfinance 결측 시 폴백값. "
              "금융주는 모델 특성상 과소평가될 수 있음.",
        "en": "🟢 LIVE: Fundamentals=yfinance (US S&P500 + Korea .KS/.KQ — market cap/FCF/debt/ROIC/income auto), "
              "Korea price=pykrx\n\n🟡 Manual (config.py): Moat qualitative tags + fallback values when "
              "yfinance is missing data. Financial stocks may score lower due to model design.",
        "ja": "🟢 LIVE：ファンダメンタルズ=yfinance（米国S&P500＋韓国.KS/.KQ — 時価総額・FCF・負債・ROIC・利益を自動取得）、"
              "韓国株価=pykrx\n\n🟡 手動（config.py）：モート定性タグ＋yfinanceデータ欠損時のフォールバック値。"
              "金融株はモデルの性質上、低評価になりやすい点にご注意ください。",
    },
    # ── 메인 헤더 & KPI ───────────────────────────────────────────────────
    "app_title": {"ko": "🏰 Dhandho 가치투자 스크리너", "en": "🏰 Dhandho Value Screener", "ja": "🏰 Dhandhoバリュー投資スクリーナー"},
    "app_caption": {
        "ko": "모니시 파브라이 『단도(Dhandho)』 — \"Heads I win, tails I don't lose much\" · 종목 {n}개 · {src}",
        "en": "Mohnish Pabrai's *The Dhandho Investor* — \"Heads I win, tails I don't lose much\" · {n} stocks · {src}",
        "ja": "モニッシュ・パブライ『ダンドー投資家』 — \"Heads I win, tails I don't lose much\" · {n}銘柄 · {src}",
    },
    "src_published": {
        "ko": "📦 배포 데이터 기준 {date} (로컬 분석본)",
        "en": "📦 Published data as of {date} (offline analysis)",
        "ja": "📦 公開データ基準 {date}（オフライン分析）",
    },
    "src_live": {
        "ko": "펀더멘털=yfinance LIVE / 한국 가격=pykrx",
        "en": "Fundamentals=yfinance LIVE / Korea price=pykrx",
        "ja": "ファンダメンタルズ=yfinance LIVE／韓国株価=pykrx",
    },
    "kpi_pass": {"ko": "✅ 조건 통과", "en": "✅ Passed filters", "ja": "✅ 条件通過"},
    "kpi_pass_delta": {"ko": "전체 {n}개 중", "en": "of {n} total", "ja": "全{n}銘柄中"},
    "kpi_avg_score": {"ko": "평균 Dhandho 점수", "en": "Avg. Dhandho score", "ja": "平均Dhandhoスコア"},
    "kpi_avg_fcf": {"ko": "평균 FCF Yield", "en": "Avg. FCF Yield", "ja": "平均FCF利回り"},
    "kpi_avg_de": {"ko": "평균 부채/자본", "en": "Avg. Debt/Equity", "ja": "平均負債/資本"},
    "kpi_wide_moat": {"ko": "와이드 해자 종목", "en": "Wide-moat stocks", "ja": "ワイドモート銘柄"},
    "unit_count": {"ko": "{n}개", "en": "{n}", "ja": "{n}件"},
    "no_pass_info": {
        "ko": "현재 임계값을 모두 통과하는 종목이 없습니다. 시장이 비싸거나 필터가 엄격합니다 — 사이드바에서 완화해 보세요.",
        "en": "No stocks currently pass all thresholds. The market may be expensive or filters too strict — try relaxing them in the sidebar.",
        "ja": "現在、すべてのしきい値を通過する銘柄がありません。市場が割高か条件が厳しすぎる可能性があります — サイドバーで緩和してみてください。",
    },
    "top_candidate_paid": {
        "ko": "🏆 최우선 후보: **{name}** ({ticker}) · Dhandho {score} · FCF Yield {fcf} · ROIC {roic} · P/E {pe} · 해자 {moat}",
        "en": "🏆 Top candidate: **{name}** ({ticker}) · Dhandho {score} · FCF Yield {fcf} · ROIC {roic} · P/E {pe} · Moat {moat}",
        "ja": "🏆 最有力候補：**{name}**（{ticker}） · Dhandho {score} · FCF利回り {fcf} · ROIC {roic} · PER {pe} · モート {moat}",
    },
    "top_candidate_free": {
        "ko": "🏆 무료 미리보기 후보 ({rank} 중): **{name}** ({ticker}) · Dhandho {score} · FCF Yield {fcf} · ROIC {roic} · P/E {pe} · 해자 {moat}",
        "en": "🏆 Free preview candidate (of {rank}): **{name}** ({ticker}) · Dhandho {score} · FCF Yield {fcf} · ROIC {roic} · P/E {pe} · Moat {moat}",
        "ja": "🏆 無料プレビュー候補（{rank}中）：**{name}**（{ticker}） · Dhandho {score} · FCF利回り {fcf} · ROIC {roic} · PER {pe} · モート {moat}",
    },
    "top_candidate_free_note": {
        "ko": "실제 1~{skip}위 최우선 후보는 유료판에서 공개됩니다.",
        "en": "The true #1–{skip} top candidates are revealed in the paid tier.",
        "ja": "実際の1〜{skip}位の最有力候補は有料版で公開されます。",
    },
    "no_preview_info": {
        "ko": "무료 미리보기 구간({rank})에 해당하는 통과 종목이 없습니다.",
        "en": "No stocks fall within the free preview range ({rank}).",
        "ja": "無料プレビュー範囲（{rank}）に該当する通過銘柄がありません。",
    },
    # ── 구독 신청 ─────────────────────────────────────────────────────────
    "signup_header": {"ko": "📬 뉴스레터 구독 신청", "en": "📬 Subscribe to the newsletter", "ja": "📬 ニュースレター購読申込"},
    "signup_body": {
        "ko": "**무료 구독**: 매주 스크리닝 결과 요약을 이메일로 받아보세요 (지금 통과 종목 중 "
              "**{rank}** 미리보기 수준의 무료판 뉴스레터).\n\n"
              "**유료판 얼리버드**: 아직 출시 전입니다. 유료판에서는 **조건 통과 종목 전체·CSV 다운로드·"
              "전주 대비 변화 추적**까지 제공할 예정이며, **지금 등록하시면 정식 가격이 얼마로 정해지든 "
              "그 가격에서 평생 할인**을 적용해 드립니다.",
        "en": "**Free subscription**: Get a weekly summary of screening results by email (same preview "
              "level as the free tier: **{rank}**).\n\n"
              "**Paid early-bird**: Not launched yet. The paid tier will include **the full list of "
              "passing stocks, CSV download, and week-over-week change tracking**. **Sign up now and "
              "lock in a lifetime discount** off whatever the launch price ends up being.",
        "ja": "**無料購読**：毎週のスクリーニング結果サマリーをメールでお届けします（現在通過中の銘柄のうち"
              "**{rank}**のプレビュー水準の無料版ニュースレター）。\n\n"
              "**有料版アーリーバード**：まだリリース前です。有料版では**条件通過銘柄の全リスト・CSVダウンロード・"
              "前週比の変化トラッキング**まで提供予定で、**今登録すると正式価格がいくらになっても"
              "その価格の永久割引**が適用されます。",
    },
    "signup_free_option": {"ko": "무료 구독", "en": "Free subscription", "ja": "無料購読"},
    "signup_waitlist_option": {"ko": "유료판 얼리버드 대기", "en": "Paid early-bird waitlist", "ja": "有料版アーリーバード待機"},
    "signup_email_placeholder": {"ko": "you@example.com", "en": "you@example.com", "ja": "you@example.com"},
    "signup_submit_button": {"ko": "📮 신청하기", "en": "📮 Submit", "ja": "📮 申し込む"},
    "msg_invalid_email": {
        "ko": "이메일 형식을 확인해 주세요.", "en": "Please check the email format.", "ja": "メールアドレスの形式をご確認ください。"},
    "msg_not_configured": {
        "ko": "신청이 아직 준비 중입니다. 잠시 후 다시 시도해 주세요.",
        "en": "Signup isn't ready yet — please try again shortly.",
        "ja": "お申し込みはまだ準備中です。しばらくしてから再度お試しください。",
    },
    "msg_error": {
        "ko": "등록 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.",
        "en": "Something went wrong while registering — please try again shortly.",
        "ja": "登録中に問題が発生しました。しばらくしてから再度お試しください。",
    },
    "msg_success_free": {
        "ko": "무료 뉴스레터 구독이 완료되었습니다 — 매주 새 스크리닝 결과를 보내드립니다.",
        "en": "You're subscribed to the free newsletter — we'll send new screening results every week.",
        "ja": "無料ニュースレターの購読が完了しました — 毎週新しいスクリーニング結果をお届けします。",
    },
    "msg_success_waitlist": {
        "ko": "얼리버드 대기자로 등록되었습니다 — 유료판 출시 시 평생 할인가로 안내드립니다.",
        "en": "You're on the early-bird waitlist — we'll notify you with a lifetime discount when the paid tier launches.",
        "ja": "アーリーバード待機リストに登録されました — 有料版リリース時に永久割引価格でご案内します。",
    },
    # ── 탭 ───────────────────────────────────────────────────────────────
    "tab1": {"ko": "📋 스크리닝 결과", "en": "📋 Screening results", "ja": "📋 スクリーニング結果"},
    "tab2": {"ko": "📊 분석 차트", "en": "📊 Charts", "ja": "📊 分析チャート"},
    "tab3": {"ko": "🔬 종목 상세", "en": "🔬 Stock detail", "ja": "🔬 銘柄詳細"},
    "tab4": {"ko": "🔄 신규/탈락(주간 스냅샷)", "en": "🔄 New/dropped (weekly snapshot)", "ja": "🔄 新規/除外（週次スナップショット）"},
    "tab5": {"ko": "🩺 포트폴리오 건강검진", "en": "🩺 Portfolio health check", "ja": "🩺 ポートフォリオ健康診断"},
    # ── 탭1: 스크리닝 결과 ────────────────────────────────────────────────
    "only_pass_checkbox": {"ko": "조건 통과 종목만 보기", "en": "Show only passing stocks", "ja": "条件通過銘柄のみ表示"},
    "free_preview_notice": {
        "ko": "무료판은 통과 종목 미리보기({rank})만 제공됩니다. 전체 유니버스는 유료판에서 열립니다.",
        "en": "The free tier only shows a preview of passing stocks ({rank}). The full universe unlocks in the paid tier.",
        "ja": "無料版では通過銘柄のプレビュー（{rank}）のみ提供されます。全ユニバースは有料版で解放されます。",
    },
    "col_market": {"ko": "시장", "en": "Market", "ja": "市場"},
    "col_ticker": {"ko": "코드", "en": "Ticker", "ja": "コード"},
    "col_name": {"ko": "종목", "en": "Name", "ja": "銘柄"},
    "col_moat": {"ko": "해자", "en": "Moat", "ja": "モート"},
    "col_dhandho": {"ko": "Dhandho점수", "en": "Dhandho score", "ja": "Dhandhoスコア"},
    "col_ai_score": {"ko": "AI점수", "en": "AI score", "ja": "AIスコア"},
    "col_ai_band": {"ko": "AI밴드", "en": "AI band", "ja": "AIバンド"},
    "col_fcf": {"ko": "FCF수익률%", "en": "FCF Yield%", "ja": "FCF利回り%"},
    "col_pfcf": {"ko": "P/FCF", "en": "P/FCF", "ja": "P/FCF"},
    "col_de": {"ko": "부채/자본", "en": "Debt/Equity", "ja": "負債/資本"},
    "col_ndebitda": {"ko": "순부채/EBITDA", "en": "NetDebt/EBITDA", "ja": "純負債/EBITDA"},
    "col_roic": {"ko": "ROIC%", "en": "ROIC%", "ja": "ROIC%"},
    "col_gm": {"ko": "매출총이익%", "en": "Gross margin%", "ja": "売上総利益率%"},
    "col_pe": {"ko": "P/E", "en": "P/E", "ja": "PER"},
    "col_pb": {"ko": "P/B", "en": "P/B", "ja": "PBR"},
    "col_ey": {"ko": "이익수익률%", "en": "Earnings yield%", "ja": "益回り%"},
    "col_downside": {"ko": "하방방어", "en": "Downside score", "ja": "下方防御"},
    "col_passes": {"ko": "통과", "en": "Pass", "ja": "通過"},
    "table_legend": {
        "ko": "🟩 통과 · Dhandho점수 75↑ 진녹/50↑ 노랑 · 🟦 해자(wide/narrow) · "
              "기본 통과 규칙: 4개 축 중 3개 이상 충족 + **부채 축 필수**. "
              "AI점수는 별도 산식(포인트 합산 방식)의 보조 지표(교차검증용, 통과 판정 미반영).",
        "en": "🟩 Pass · Dhandho score 75+ dark green / 50+ yellow · 🟦 Moat (wide/narrow) · "
              "Default pass rule: 3 of 4 axes + **debt axis mandatory**. "
              "AI score is a secondary metric from a different formula (point-based, cross-check only, not used for pass/fail).",
        "ja": "🟩 通過 · Dhandhoスコア75以上は濃緑／50以上は黄色 · 🟦 モート（wide/narrow） · "
              "基本通過ルール：4軸中3軸以上を満たす＋**負債軸は必須**。"
              "AIスコアは別方式（ポイント合算方式）の補助指標（クロスチェック用、通過判定には使用しません）。",
    },
    "lock_hidden": {
        "ko": "나머지 **{n}개** 통과 종목·전체 순위·CSV는 유료판(사이드바 이메일/백업 코드)에서 열립니다.",
        "en": "The remaining **{n}** passing stocks, full rankings, and CSV unlock in the paid tier (sidebar email/backup code).",
        "ja": "残り**{n}件**の通過銘柄・全ランキング・CSVは有料版（サイドバーのメール／バックアップコード）で解放されます。",
    },
    "lock_generic": {
        "ko": "유료판에서 전체 순위·CSV를 열 수 있습니다.",
        "en": "Unlock full rankings and CSV in the paid tier.",
        "ja": "有料版で全ランキング・CSVを解放できます。",
    },
    "csv_button": {"ko": "⬇️ 전체 결과 CSV 다운로드 (유료판)", "en": "⬇️ Download full results CSV (paid)", "ja": "⬇️ 全結果CSVダウンロード（有料版）"},
    "no_data_error": {
        "ko": "표시할 데이터가 없습니다.", "en": "No data to display.", "ja": "表示するデータがありません。"},
    "no_data_hint": {
        "ko": " 사이드바에서 시장/종목 수를 조정하거나 새로고침하세요.",
        "en": " Try adjusting the market/scan count in the sidebar, or refresh.",
        "ja": " サイドバーで市場／銘柄数を調整するか、更新してください。",
    },
    # ── 푸터 ─────────────────────────────────────────────────────────────
    "footer_disclaimer": {
        "ko": "⚠️ 본 대시보드는 정보 제공용이며 투자 권유가 아닙니다. 해자(Moat)는 본질적으로 정성 판단이며 "
              "여기서는 ROIC·마진 안정성·수동 태그로 근사한 보조 지표입니다. 펀더멘털은 yfinance(미국·한국·일본) "
              "자동 수집값으로 지연·오류가 있을 수 있으니, 실제 판단 전 DART·FnGuide·증권사 리포트로 반드시 검증하세요.",
        "en": "⚠️ This dashboard is for informational purposes only and is not investment advice. "
              "Moat is inherently a qualitative judgment; here it's approximated via ROIC, margin stability, "
              "and manual tags. Fundamentals are auto-collected via yfinance (US/Korea/Japan) and may be "
              "delayed or inaccurate — always verify with primary filings before making decisions.",
        "ja": "⚠️ 本ダッシュボードは情報提供のみを目的としており、投資勧誘ではありません。モートは本質的に定性的な"
              "判断であり、ここではROIC・マージン安定性・手動タグによる近似指標を用いています。ファンダメンタルズは"
              "yfinance（米国・韓国・日本）による自動収集値のため遅延や誤りがある可能性があります。実際の判断の前に"
              "必ず一次情報（開示資料等）でご確認ください。",
    },
}


def lang() -> str:
    return st.session_state.get("lang", "ko")


def set_lang(code: str) -> None:
    st.session_state["lang"] = code


def t(key: str, **kwargs) -> str:
    """번역 문자열 조회. kwargs 가 있으면 .format() 치환."""
    entry = _S.get(key)
    if entry is None:
        return key
    template = entry.get(lang()) or entry.get("ko", key)
    return template.format(**kwargs) if kwargs else template


def rank_label() -> str:
    """무료 미리보기 순위 구간 라벨 (예: '6~10위' / '#6-10' / '6〜10位')."""
    lo = config.FREE_TIER_SKIP + 1
    hi = config.FREE_TIER_SKIP + config.FREE_TIER_LIMIT
    return {
        "ko": f"{lo}~{hi}위",
        "en": f"#{lo}-{hi}",
        "ja": f"{lo}〜{hi}位",
    }.get(lang(), f"{lo}~{hi}위")


def free_preview_caption() -> str:
    return {
        "ko": f"무료 미리보기: 통과 종목 중 Dhandho 순 **{rank_label()}** "
              f"({config.FREE_TIER_LIMIT}종목). **1~{config.FREE_TIER_SKIP}위·전체 순위**는 유료판.",
        "en": f"Free preview: passing stocks ranked **{rank_label()}** by Dhandho score "
              f"({config.FREE_TIER_LIMIT} stocks). **Ranks 1-{config.FREE_TIER_SKIP} and the full ranking** are paid-tier only.",
        "ja": f"無料プレビュー：通過銘柄のうちDhandho順**{rank_label()}**"
              f"（{config.FREE_TIER_LIMIT}銘柄）。**1〜{config.FREE_TIER_SKIP}位・全ランキング**は有料版限定。",
    }.get(lang())
