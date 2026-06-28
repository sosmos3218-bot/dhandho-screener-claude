# -*- coding: utf-8 -*-
"""
포트폴리오 입력 파일 입출력 (건강검진용)
========================================
  - 사용자가 받아 채울 수 있는 기본 입력 템플릿(xlsx/csv) 생성
  - 업로드한 xlsx/csv 에서 티커(+선택: 보유수량/평균단가) 파싱

티커 형식: 미국=AAPL · 한국=005930(6자리) · 일본=7203.T(.T)
보유수량/평균단가는 선택 — 있으면 포트폴리오 가중 요약에 사용(정보 제공용).
"""
import io

import pandas as pd

COLS = ["티커", "종목명(선택)", "보유수량(선택)", "평균단가(선택)"]

_TEMPLATE_ROWS = [
    {"티커": "AAPL", "종목명(선택)": "Apple", "보유수량(선택)": 10, "평균단가(선택)": 180},
    {"티커": "005930", "종목명(선택)": "삼성전자", "보유수량(선택)": 50, "평균단가(선택)": 70000},
    {"티커": "7203.T", "종목명(선택)": "도요타", "보유수량(선택)": 20, "평균단가(선택)": 2500},
    {"티커": "KO", "종목명(선택)": "코카콜라", "보유수량(선택)": 30, "평균단가(선택)": 60},
]

# 컬럼 자동 인식 키워드 (대소문자 무시, 부분일치)
_TICKER_KEYS = ["티커", "ticker", "종목코드", "코드", "symbol", "종목"]
_QTY_KEYS = ["보유수량", "수량", "quantity", "qty", "주수"]
_PRICE_KEYS = ["평균단가", "평단", "매입가", "avg", "cost", "단가"]


def template_df() -> pd.DataFrame:
    return pd.DataFrame(_TEMPLATE_ROWS, columns=COLS)


def template_xlsx_bytes() -> bytes:
    """다운로드용 xlsx 바이트 (시트명 portfolio)."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        template_df().to_excel(w, index=False, sheet_name="portfolio")
    return buf.getvalue()


def template_csv_bytes() -> bytes:
    """다운로드용 csv 바이트 (엑셀 한글 호환 위해 utf-8-sig)."""
    return template_df().to_csv(index=False).encode("utf-8-sig")


def _match_col(columns, keys):
    """columns 중 keys 키워드를 (부분, 대소문자무시) 포함하는 첫 컬럼명 반환."""
    for c in columns:
        cl = str(c).strip().lower()
        for k in keys:
            if k.lower() in cl:
                return c
    return None


def parse_upload(file) -> pd.DataFrame:
    """
    업로드 파일(xlsx/csv) → 표준 컬럼 DataFrame[ticker, qty, avg_price].
    티커 컬럼을 못 찾으면 ValueError.
    """
    name = getattr(file, "name", "").lower()
    if name.endswith(".csv"):
        df = pd.read_csv(file)
    elif name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(file)  # openpyxl
    else:
        raise ValueError("지원하지 않는 형식입니다. .xlsx 또는 .csv 를 올려주세요.")

    if df.empty:
        raise ValueError("파일에 데이터가 없습니다.")

    tcol = _match_col(df.columns, _TICKER_KEYS)
    if tcol is None:
        # 컬럼명이 없으면 첫 열을 티커로 간주
        tcol = df.columns[0]
    qcol = _match_col(df.columns, _QTY_KEYS)
    pcol = _match_col(df.columns, _PRICE_KEYS)

    out = pd.DataFrame()
    out["ticker"] = (df[tcol].astype(str).str.strip()
                     .replace({"nan": "", "None": ""}))
    out = out[out["ticker"] != ""]
    out["qty"] = pd.to_numeric(df[qcol], errors="coerce") if qcol else pd.NA
    out["avg_price"] = pd.to_numeric(df[pcol], errors="coerce") if pcol else pd.NA
    return out.reset_index(drop=True)
