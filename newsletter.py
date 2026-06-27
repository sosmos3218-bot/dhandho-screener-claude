# -*- coding: utf-8 -*-
"""
주간 Dhandho 뉴스레터 생성기 (+ opt-in SMTP 발송)
=================================================
최신 스냅샷(snapshots/dhandho_*.json)과 직전 스냅샷을 비교해
교육형·규제 안전 톤의 뉴스레터를 HTML + 마크다운으로 생성한다.

사용:
    python newsletter.py            # 생성만 (newsletter/ 폴더)
    python newsletter.py --send     # 생성 + SMTP 발송 (secrets.json 필요)

규제 안전 원칙:
  - 특정 종목 "매수 추천"이 아니라 *정량 기준 통과 목록 + 교육적 해설* 형식
  - 모든 발행물에 정보제공·비투자권유 면책 + 데이터 출처 명시
"""
import datetime as dt
import glob
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
SNAP_DIR = os.path.join(BASE, "snapshots")
OUT_DIR = os.path.join(BASE, "newsletter")
SECRETS = os.path.join(BASE, "secrets.json")

BRAND = "단도(Dhandho) 위클리"
TAGLINE = "Heads I win, tails I don't lose much — 강한 현금흐름·낮은 부채·해자·저평가"

# 매주 돌아가며 노출하는 교육 코너 (Dhandho 4축)
EDU_SNIPPETS = [
    ("💰 시총 대비 현금흐름 (FCF Yield)",
     "기업이 1년에 벌어들이는 잉여현금(영업현금흐름−설비투자)을 시가총액으로 나눈 값입니다. "
     "높을수록 '버는 돈에 비해 싸다'는 뜻이에요. 파브라이는 회계상 이익보다 실제 현금 창출력을 봅니다."),
    ("🛡️ 낮은 부채 (Debt/Equity)",
     "Dhandho의 핵심은 '잃지 않는 것(tails I don't lose much)'. 부채가 적은 기업은 불황에도 "
     "버틸 체력이 있습니다. 부채/자본 0.5 이하를 통과 필수 조건으로 둔 이유입니다."),
    ("🏰 독점적 해자 (Moat)",
     "경쟁자가 쉽게 뺏지 못하는 구조적 우위(브랜드·전환비용·규모·네트워크). 정량적으로는 "
     "높고 안정적인 ROIC와 마진으로 드러납니다. 해자가 있어야 저평가가 '함정'이 아닌 '기회'가 됩니다."),
    ("🎯 안전마진 (저평가)",
     "좋은 기업도 비싸게 사면 위험합니다. 낮은 P/E·P/B, 높은 이익수익률(EBIT/EV)로 "
     "내재가치보다 충분히 싼지 확인합니다. '동전 던지기에서 앞면이면 크게 벌고 뒷면이어도 조금만 잃는' 구조."),
]


# ──────────────────────────────────────────────────────────────────────────
# 데이터 로드 / diff
# ──────────────────────────────────────────────────────────────────────────
def load_snapshots():
    files = sorted(glob.glob(os.path.join(SNAP_DIR, "dhandho_*.json")))
    if not files:
        return None, None
    latest = json.load(open(files[-1], encoding="utf-8"))
    prev = json.load(open(files[-2], encoding="utf-8")) if len(files) >= 2 else None
    return latest, prev


def compute_diff(latest, prev):
    cur = {r["ticker"]: r for r in latest["passes"]}
    old = {r["ticker"]: r for r in (prev["passes"] if prev else [])}
    new = sorted([cur[t] for t in cur if t not in old], key=lambda x: -x["dhandho_score"])
    dropped = sorted([old[t] for t in old if t not in cur], key=lambda x: -x["dhandho_score"])
    return new, dropped


def market_comment(n_pass, total):
    ratio = (n_pass / total * 100) if total else 0
    if ratio < 3:
        return ("🔴 시장 전반이 비쌉니다.", "조건을 통과하는 종목이 드뭅니다. "
                "Dhandho 관점에선 '지금은 인내할 때'라는 신호 — 무리해서 사기보다 현금을 쥐고 기다립니다.")
    if ratio < 8:
        return ("🟠 선별적 기회 구간.", "전반적으로 싸지 않지만 일부 종목이 기준을 통과합니다. "
                "통과 종목을 깊이 들여다볼 가치가 있는 시점.")
    return ("🟢 기회가 늘어나는 구간.", "다수 종목이 기준을 통과합니다. 과거 약세장에서 자주 나타난 "
            "패턴 — 우량 기업을 헐값에 담을 기회가 많아집니다.")


def week_index():
    """교육 코너 로테이션 인덱스 (ISO 주차 기준)."""
    return dt.date.today().isocalendar()[1] % len(EDU_SNIPPETS)


# ──────────────────────────────────────────────────────────────────────────
# 마크다운 (스티비/Substack 붙여넣기용)
# ──────────────────────────────────────────────────────────────────────────
def build_markdown(latest, prev):
    date = latest["date"]
    n_pass, total = latest["n_pass"], latest["total_scanned"]
    new, dropped = compute_diff(latest, prev)
    head, body = market_comment(n_pass, total)
    edu_title, edu_body = EDU_SNIPPETS[week_index()]

    L = [f"# {BRAND} — {date}", "", f"_{TAGLINE}_", "",
         f"이번 주 **{total}개** 종목을 정량 스캔해 **{n_pass}개**가 Dhandho 4축 기준을 통과했습니다.", "",
         f"## 📊 시장 온도  {head}", body, "",
         f"## 🆕 이번 주 신규 진입 ({len(new)})"]
    if new:
        for r in new:
            L.append(f"- **{r['name']}** ({r['ticker']}, {r['market']}) — "
                     f"Dhandho {r['dhandho_score']} · FCF수익률 {r['fcf_yield']}% · "
                     f"부채/자본 {r['debt_equity']} · ROIC {r['roic']}% · P/E {r['pe']} · 해자 {r['moat_tag']}")
    else:
        L.append("- 없음 (지난주 대비 변화 없음)")

    L += ["", f"## ❌ 이번 주 탈락 ({len(dropped)})"]
    if dropped:
        for r in dropped:
            L.append(f"- **{r['name']}** ({r['ticker']}) — 직전 Dhandho {r['dhandho_score']} "
                     f"(가격 상승으로 저평가 해소 / 펀더멘털 변화 등 추정)")
    else:
        L.append("- 없음")

    L += ["", "## ✅ 현재 통과 종목 Top 15 (Dhandho 순)", "",
          "| # | 종목 | 시장 | Dhandho | FCF수익률 | 부채/자본 | ROIC | P/E | 해자 |",
          "|--:|------|:--:|--:|--:|--:|--:|--:|:--:|"]
    for i, r in enumerate(sorted(latest["passes"], key=lambda x: -x["dhandho_score"])[:15], 1):
        L.append(f"| {i} | {r['name']} ({r['ticker']}) | {r['market']} | {r['dhandho_score']} | "
                 f"{r['fcf_yield']}% | {r['debt_equity']} | {r['roic']}% | {r['pe']} | {r['moat_tag']} |")

    L += ["", f"## 📚 이번 주 가치투자 한 조각 — {edu_title}", edu_body, "",
          "---", "",
          "⚠️ **면책**: 본 뉴스레터는 정량 스크리닝 결과를 공유하는 **정보 제공·교육 목적** 콘텐츠이며, "
          "특정 종목의 매수·매도를 권유하지 않습니다. 투자 판단과 책임은 전적으로 본인에게 있습니다. "
          "데이터: yfinance·pykrx (지연/오류 가능), 해자 태그는 운영자의 정성 판단입니다. "
          "투자 전 DART·FnGuide 등 1차 자료로 반드시 검증하세요.",
          "", f"_구독 해지를 원하시면 회신 주세요. · {BRAND}_"]
    return "\n".join(L)


# ──────────────────────────────────────────────────────────────────────────
# HTML (이메일/플랫폼용, 인라인 스타일)
# ──────────────────────────────────────────────────────────────────────────
def _row_html(r, rank=None):
    moat_color = {"wide": "#1565c0", "narrow": "#5e92d6", "none": "#9e9e9e"}.get(r["moat_tag"], "#9e9e9e")
    rank_cell = f'<td style="padding:8px 6px;color:#9aa0a6;font-size:12px;text-align:center;">{rank}</td>' if rank else ""
    return (
        f'<tr style="border-bottom:1px solid #eee;">'
        f'{rank_cell}'
        f'<td style="padding:8px 6px;"><b style="color:#1a1a1a;">{r["name"]}</b>'
        f'<span style="color:#9aa0a6;font-size:12px;"> {r["ticker"]}·{r["market"]}</span></td>'
        f'<td style="padding:8px 6px;text-align:right;"><b style="color:#188038;">{r["dhandho_score"]}</b></td>'
        f'<td style="padding:8px 6px;text-align:right;color:#333;">{r["fcf_yield"]}%</td>'
        f'<td style="padding:8px 6px;text-align:right;color:#333;">{r["debt_equity"]}</td>'
        f'<td style="padding:8px 6px;text-align:right;color:#333;">{r["roic"]}%</td>'
        f'<td style="padding:8px 6px;text-align:right;color:#333;">{r["pe"]}</td>'
        f'<td style="padding:8px 6px;text-align:center;"><span style="background:{moat_color};color:#fff;'
        f'border-radius:10px;padding:1px 8px;font-size:11px;">{r["moat_tag"]}</span></td>'
        f'</tr>'
    )


def build_html(latest, prev):
    date = latest["date"]
    n_pass, total = latest["n_pass"], latest["total_scanned"]
    new, dropped = compute_diff(latest, prev)
    head, body = market_comment(n_pass, total)
    edu_title, edu_body = EDU_SNIPPETS[week_index()]

    def section(title):
        return (f'<h2 style="font-size:17px;color:#1a1a1a;margin:28px 0 10px;'
                f'border-left:4px solid #188038;padding-left:10px;">{title}</h2>')

    new_html = "".join(
        f'<li style="margin:6px 0;"><b>{r["name"]}</b> '
        f'<span style="color:#9aa0a6;font-size:12px;">{r["ticker"]}·{r["market"]}</span><br>'
        f'<span style="font-size:13px;color:#444;">Dhandho {r["dhandho_score"]} · '
        f'FCF {r["fcf_yield"]}% · 부채/자본 {r["debt_equity"]} · ROIC {r["roic"]}% · '
        f'P/E {r["pe"]} · 해자 {r["moat_tag"]}</span></li>'
        for r in new) or '<li style="color:#9aa0a6;">없음 (지난주 대비 변화 없음)</li>'

    dropped_html = "".join(
        f'<li style="margin:6px 0;"><b>{r["name"]}</b> '
        f'<span style="color:#9aa0a6;font-size:12px;">{r["ticker"]}</span> — '
        f'<span style="font-size:13px;color:#444;">직전 Dhandho {r["dhandho_score"]}</span></li>'
        for r in dropped) or '<li style="color:#9aa0a6;">없음</li>'

    top_rows = "".join(_row_html(r, i) for i, r in
                       enumerate(sorted(latest["passes"], key=lambda x: -x["dhandho_score"])[:15], 1))

    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f4f5f7;font-family:-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;">
<div style="max-width:600px;margin:0 auto;background:#ffffff;">

  <!-- 헤더 -->
  <div style="background:linear-gradient(135deg,#188038,#0b5e28);padding:28px 24px;color:#fff;">
    <div style="font-size:13px;opacity:.85;">🏰 {date}</div>
    <div style="font-size:24px;font-weight:800;margin-top:4px;">{BRAND}</div>
    <div style="font-size:12px;opacity:.85;margin-top:6px;line-height:1.5;">{TAGLINE}</div>
  </div>

  <div style="padding:24px;">
    <p style="font-size:15px;color:#333;line-height:1.6;margin:0 0 8px;">
      이번 주 <b>{total}개</b> 종목을 정량 스캔해 <b style="color:#188038;">{n_pass}개</b>가
      Dhandho 4축 기준을 통과했습니다.</p>

    <!-- 시장 온도 -->
    <div style="background:#f1f8f3;border-radius:10px;padding:14px 16px;margin:14px 0;">
      <div style="font-size:15px;font-weight:700;color:#1a1a1a;">📊 시장 온도 — {head}</div>
      <div style="font-size:13px;color:#444;line-height:1.6;margin-top:4px;">{body}</div>
    </div>

    {section(f"🆕 이번 주 신규 진입 ({len(new)})")}
    <ul style="padding-left:18px;margin:0;font-size:14px;color:#1a1a1a;">{new_html}</ul>

    {section(f"❌ 이번 주 탈락 ({len(dropped)})")}
    <ul style="padding-left:18px;margin:0;font-size:14px;color:#1a1a1a;">{dropped_html}</ul>

    {section("✅ 현재 통과 종목 Top 15")}
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <thead><tr style="background:#fafafa;color:#666;font-size:11px;text-align:right;">
        <th style="padding:6px;text-align:center;">#</th>
        <th style="padding:6px;text-align:left;">종목</th>
        <th style="padding:6px;">Dhandho</th><th style="padding:6px;">FCF</th>
        <th style="padding:6px;">부채/자본</th><th style="padding:6px;">ROIC</th>
        <th style="padding:6px;">P/E</th><th style="padding:6px;text-align:center;">해자</th>
      </tr></thead>
      <tbody>{top_rows}</tbody>
    </table>

    <!-- 교육 코너 -->
    <div style="background:#fff8e1;border-radius:10px;padding:16px;margin:24px 0;">
      <div style="font-size:15px;font-weight:700;color:#7a5c00;">📚 이번 주 가치투자 한 조각</div>
      <div style="font-size:14px;font-weight:700;color:#1a1a1a;margin-top:8px;">{edu_title}</div>
      <div style="font-size:13px;color:#444;line-height:1.7;margin-top:4px;">{edu_body}</div>
    </div>

    <!-- 면책 -->
    <div style="border-top:1px solid #eee;margin-top:24px;padding-top:16px;font-size:11px;color:#9aa0a6;line-height:1.6;">
      ⚠️ 본 뉴스레터는 정량 스크리닝 결과를 공유하는 <b>정보 제공·교육 목적</b> 콘텐츠이며,
      특정 종목의 매수·매도를 권유하지 않습니다. 투자 판단과 책임은 전적으로 본인에게 있습니다.
      데이터: yfinance·pykrx(지연/오류 가능), 해자 태그는 운영자의 정성 판단입니다.
      투자 전 DART·FnGuide 등 1차 자료로 반드시 검증하세요.<br><br>
      구독 해지를 원하시면 본 메일에 회신해 주세요. · {BRAND}
    </div>
  </div>
</div>
</body></html>"""


# ──────────────────────────────────────────────────────────────────────────
# 생성 / 발송
# ──────────────────────────────────────────────────────────────────────────
def generate():
    latest, prev = load_snapshots()
    if latest is None:
        print("⚠️ 스냅샷이 없습니다. 먼저 snapshot.py 를 실행하세요.")
        return None
    os.makedirs(OUT_DIR, exist_ok=True)
    date = latest["date"]
    md = build_markdown(latest, prev)
    html = build_html(latest, prev)
    md_path = os.path.join(OUT_DIR, f"dhandho_{date}.md")
    html_path = os.path.join(OUT_DIR, f"dhandho_{date}.html")
    open(md_path, "w", encoding="utf-8").write(md)
    open(html_path, "w", encoding="utf-8").write(html)
    print(f"✅ 뉴스레터 생성: {md_path}")
    print(f"✅ 뉴스레터 생성: {html_path}")
    return {"date": date, "md": md, "html": html,
            "subject": f"[{BRAND}] {date} — 통과 {latest['n_pass']}종목"}


def send(payload):
    """secrets.json 의 SMTP 설정으로 구독자에게 발송 (opt-in)."""
    if not os.path.exists(SECRETS):
        print("ℹ️ secrets.json 이 없어 발송을 건너뜁니다 (생성만 완료). "
              "발송하려면 secrets.example.json 을 참고해 secrets.json 을 만드세요.")
        return False
    import smtplib
    import ssl
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    cfg = json.load(open(SECRETS, encoding="utf-8"))
    smtp = cfg.get("smtp", {})
    subscribers = cfg.get("subscribers", [])
    if not subscribers:
        print("ℹ️ secrets.json 에 subscribers 가 비어있어 발송하지 않습니다.")
        return False

    host = smtp.get("host", "smtp.gmail.com")
    port = int(smtp.get("port", 465))
    user = smtp["user"]
    pw = smtp["password"]
    from_name = smtp.get("from_name", BRAND)

    ctx = ssl.create_default_context()
    sent = 0
    with smtplib.SMTP_SSL(host, port, context=ctx) as server:
        server.login(user, pw)
        for to in subscribers:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = payload["subject"]
            msg["From"] = f"{from_name} <{user}>"
            msg["To"] = to
            msg.attach(MIMEText(payload["md"], "plain", "utf-8"))
            msg.attach(MIMEText(payload["html"], "html", "utf-8"))
            server.sendmail(user, to, msg.as_string())
            sent += 1
    print(f"📧 발송 완료: {sent}명 ({host})")
    return True


if __name__ == "__main__":
    payload = generate()
    if payload and "--send" in sys.argv:
        send(payload)
