# -*- coding: utf-8 -*-
"""
주간 스냅샷 & diff 생성기
=========================
전체 유니버스를 스캔해 Dhandho 조건 통과 종목을 snapshots/ 에 저장하고,
직전 스냅샷과 비교해 신규 진입 / 탈락 종목을 마크다운으로 기록한다.

사용:
    python snapshot.py            # 전체(ALL) 스캔
    python snapshot.py US 30      # 미국 상위 30개만

cron / 주간 스케줄(SKILL.md)이 이 스크립트를 호출한다.
"""
import datetime as dt
import json
import os
import sys

import screening

SNAP_DIR = os.path.join(os.path.dirname(__file__), "snapshots")
os.makedirs(SNAP_DIR, exist_ok=True)

_KEEP = ["market", "ticker", "name", "moat_tag", "dhandho_score",
         "fcf_yield", "debt_equity", "roic", "pe", "earnings_yield",
         "downside_score"]


def _clean(row: dict) -> dict:
    out = {}
    for k in _KEEP:
        v = row.get(k)
        out[k] = round(v, 2) if isinstance(v, float) else v
    out["flags"] = row.get("flags", [])
    return out


def run(market="ALL", limit=None):
    today = dt.date.today().isoformat()
    print(f"[{today}] Dhandho 스냅샷 시작 (market={market}, limit={limit}) ...")
    df = screening.build_universe(market, use_cache=False, limit=limit)
    if df.empty:
        print("⚠️ 수집 데이터 없음 — 중단")
        return None

    passed = [_clean(r) for r in df[df["passes"]].to_dict("records")]
    payload = {
        "date": today, "market": market,
        "total_scanned": len(df), "n_pass": len(passed),
        "passes": passed,
    }
    json_path = os.path.join(SNAP_DIR, f"dhandho_{today}.json")
    json.dump(payload, open(json_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"✅ 저장: {json_path}  (통과 {len(passed)}/{len(df)})")

    # 직전 스냅샷과 diff
    files = sorted(f for f in os.listdir(SNAP_DIR)
                   if f.startswith("dhandho_") and f.endswith(".json"))
    prev = None
    for f in reversed(files):
        if f != f"dhandho_{today}.json":
            prev = json.load(open(os.path.join(SNAP_DIR, f), encoding="utf-8"))
            break

    cur_map = {r["ticker"]: r for r in passed}
    prev_map = {r["ticker"]: r for r in (prev["passes"] if prev else [])}
    new = [cur_map[t] for t in cur_map if t not in prev_map]
    dropped = [prev_map[t] for t in prev_map if t not in cur_map]

    lines = [f"# Dhandho 스크리닝 스냅샷 — {today}", "",
             f"- 스캔 종목: **{len(df)}** · 조건 통과: **{len(passed)}**",
             f"- 직전 스냅샷: {prev['date'] if prev else '없음'}", "",
             f"## 🆕 신규 진입 ({len(new)})"]
    if new:
        lines += [f"- **{r['name']}** ({r['ticker']}) · Dhandho {r['dhandho_score']} "
                  f"· FCF {r['fcf_yield']}% · ROIC {r['roic']}% · 해자 {r['moat_tag']}"
                  for r in sorted(new, key=lambda x: -x["dhandho_score"])]
    else:
        lines.append("- 없음")
    lines += ["", f"## ❌ 탈락 ({len(dropped)})"]
    if dropped:
        lines += [f"- **{r['name']}** ({r['ticker']}) · 직전 Dhandho {r['dhandho_score']}"
                  for r in dropped]
    else:
        lines.append("- 없음")
    lines += ["", "## ✅ 현재 통과 종목 (Dhandho 순)"]
    lines += [f"{i+1}. **{r['name']}** ({r['ticker']}, {r['market']}) · "
              f"Dhandho {r['dhandho_score']} · FCF {r['fcf_yield']}% · "
              f"부채/자본 {r['debt_equity']} · ROIC {r['roic']}% · P/E {r['pe']}"
              for i, r in enumerate(sorted(passed, key=lambda x: -x["dhandho_score"]))]

    md_path = os.path.join(SNAP_DIR, f"diff_{today}.md")
    open(md_path, "w", encoding="utf-8").write("\n".join(lines))
    print(f"✅ diff: {md_path}  (신규 {len(new)} / 탈락 {len(dropped)})")
    return payload


if __name__ == "__main__":
    mkt = sys.argv[1] if len(sys.argv) > 1 else "ALL"
    lim = int(sys.argv[2]) if len(sys.argv) > 2 else None
    run(mkt, lim)
