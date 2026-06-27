# -*- coding: utf-8 -*-
"""
단도(Dhandho) 가치투자 스크리닝 대시보드 - 설정 파일
=====================================================
모니시 파브라이의 Dhandho 철학을 정량 필터로 변환한다.
  "Heads I win, tails I don't lose much" — 강한 잉여현금흐름 / 낮은 부채 /
  독점적 해자 / 깊은 안전마진(저평가) 을 가진 기업을 발굴.

[데이터 출처 구분]
  LIVE   : 접속 시 실시간 수집
           - 미국: yfinance (시가총액·FCF·부채·ROIC·마진·PER·PBR 자동)
           - 한국: pykrx (가격만 LIVE)
  INPUT  : 무료 API로 안 나와 여기에 수동 입력하는 값
           - 한국 종목 펀더멘털(FCF·부채·자본·EBITDA·ROIC·EPS·BPS)
           - 해자(Moat) 정성 태그 (wide / narrow / none)
           → FnGuide·네이버금융·사업보고서로 검증 후 갱신하고
             반드시 as_of(기준일)·source(출처)를 남길 것. (PLACEHOLDER 표시)

⚠️ 아래 INPUT 수치/태그는 프레임워크 동작용 *초기 추정치* 입니다.
   실제 투자 판단 전 반드시 검증·갱신하세요.
"""

# ──────────────────────────────────────────────────────────────────────────
# 1) Dhandho 스크리닝 임계값 (4개 축)
# ──────────────────────────────────────────────────────────────────────────
THRESHOLDS = {
    # ① 시가총액 대비 현금흐름 (강한 잉여현금흐름을 헐값에)
    "fcf_yield_min": 8.0,        # FCF Yield = FCF / 시가총액 (%) ≥ 8%
    "p_fcf_max": 15.0,           # P/FCF = 시총 / FCF ≤ 15배
    # ② 낮은 부채 (tails I don't lose much — 하방 방어)
    "debt_equity_max": 0.5,      # 총부채 / 자본 ≤ 0.5
    "netdebt_ebitda_max": 2.5,   # 순부채 / EBITDA ≤ 2.5
    # ③ 독점적 해자 (Moat — 지속 가능한 초과수익)
    "roic_min": 15.0,            # ROIC(또는 ROE) ≥ 15%
    "gross_margin_min": 40.0,    # 매출총이익률 ≥ 40%
    "margin_stability_max": 8.0, # 다년 영업이익률 표준편차 ≤ 8%p (낮을수록 안정적 해자)
    # ④ 저평가 / 안전마진
    "pe_max": 15.0,              # P/E ≤ 15
    "pb_max": 3.0,               # P/B ≤ 3
    "earnings_yield_min": 8.0,   # Earnings Yield = EBIT / EV (%) ≥ 8% (Greenblatt)
}

# 조건 통과로 인정하는 "근접" 허용 범위 (테이블 색상 하이라이트용, ±%)
NEAR_MISS_RATIO = 0.15

# 다년 안정성 계산 기간(연)
HISTORY_YEARS = 5

# ──────────────────────────────────────────────────────────────────────────
# 2) Dhandho Score 가중치 (4개 축, 합 = 1.0)
# ──────────────────────────────────────────────────────────────────────────
SCORE_WEIGHTS = {
    "cashflow": 0.35,   # ① 시총 대비 현금흐름
    "debt": 0.20,       # ② 낮은 부채
    "moat": 0.25,       # ③ 해자
    "value": 0.20,      # ④ 저평가
}

# 해자 정성 태그 → 점수 보너스(0~1 스케일에서 가산, moat 축에 반영)
MOAT_TAG_BONUS = {"wide": 0.30, "narrow": 0.15, "none": 0.0}

# ──────────────────────────────────────────────────────────────────────────
# 3) 미국 유니버스 (yfinance 자동 스캔 대상)
#    S&P 500 전체 (위키피디아 List_of_S&P_500_companies 기준, .→- 변환).
#    레이트리밋/결측은 data.py 에서 graceful skip. 대시보드 슬라이더로 스캔 수 조절,
#    주간 snapshot.py ALL 은 전체를 스캔(수 분 소요).
#    갱신: scripts 없이 위키 표를 재파싱해 이 리스트만 교체하면 됨.
# ──────────────────────────────────────────────────────────────────────────
US_UNIVERSE = [
    "MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES", "AFL", "A",
    "APD", "ABNB", "AKAM", "ALB", "ARE", "ALGN", "ALLE", "LNT", "ALL", "GOOGL",
    "GOOG", "MO", "AMZN", "AMCR", "AEE", "AEP", "AXP", "AIG", "AMT", "AWK",
    "AMP", "AME", "AMGN", "APH", "ADI", "AON", "APA", "APO", "AAPL", "AMAT",
    "APP", "APTV", "ACGL", "ADM", "ARES", "ANET", "AJG", "AIZ", "T", "ATO",
    "ADSK", "ADP", "AZO", "AVB", "AVY", "AXON", "BKR", "BALL", "BAC", "BAX",
    "BDX", "BRK-B", "BBY", "TECH", "BIIB", "BLK", "BX", "XYZ", "BNY", "BA",
    "BKNG", "BSX", "BMY", "AVGO", "BR", "BRO", "BF-B", "BLDR", "BG", "BXP",
    "CHRW", "CDNS", "CPT", "COF", "CAH", "CCL", "CARR", "CVNA", "CASY", "CAT",
    "CBRE", "CDW", "COR", "CNC", "CNP", "CF", "CRL", "SCHW", "CHTR", "CVX",
    "CMG", "CB", "CHD", "CIEN", "CI", "CINF", "CTAS", "CSCO", "C", "CFG",
    "CLX", "CME", "CMS", "KO", "CTSH", "COHR", "COIN", "CL", "CMCSA", "FIX",
    "CAG", "COP", "ED", "STZ", "CEG", "COO", "CPRT", "GLW", "CPAY", "CTVA",
    "CSGP", "COST", "CRH", "CRWD", "CCI", "CSX", "CMI", "CVS", "DHR", "DRI",
    "DDOG", "DVA", "DECK", "DE", "DELL", "DAL", "DVN", "DXCM", "FANG", "DLR",
    "DG", "DLTR", "D", "DPZ", "DASH", "DOV", "DOW", "DHI", "DTE", "DUK",
    "DD", "ETN", "EBAY", "ECHO", "ECL", "EIX", "EW", "EA", "ELV", "EME",
    "EMR", "ETR", "EOG", "EQT", "EFX", "EQIX", "EQR", "ERIE", "ESS", "EL",
    "EG", "EVRG", "ES", "EXC", "EXE", "EXPE", "EXPD", "EXR", "XOM", "FFIV",
    "FDS", "FICO", "FAST", "FRT", "FDX", "FDXF", "FIS", "FITB", "FSLR", "FE",
    "FISV", "FLEX", "F", "FTNT", "FTV", "FOXA", "FOX", "BEN", "FCX", "GRMN",
    "IT", "GE", "GEHC", "GEV", "GEN", "GNRC", "GD", "GIS", "GM", "GPC",
    "GILD", "GPN", "GL", "GDDY", "GS", "HAL", "HIG", "HAS", "HCA", "DOC",
    "HSIC", "HSY", "HPE", "HLT", "HD", "HON", "HRL", "HST", "HWM", "HPQ",
    "HUBB", "HUM", "HBAN", "HII", "IBM", "IEX", "IDXX", "ITW", "INCY", "IR",
    "PODD", "INTC", "IBKR", "ICE", "IFF", "IP", "INTU", "ISRG", "IVZ", "INVH",
    "IQV", "IRM", "JBHT", "JBL", "JKHY", "J", "JNJ", "JCI", "JPM", "KVUE",
    "KDP", "KEY", "KEYS", "KMB", "KIM", "KMI", "KKR", "KLAC", "KHC", "KR",
    "LHX", "LH", "LRCX", "LVS", "LDOS", "LEN", "LII", "LLY", "LIN", "LYV",
    "LMT", "L", "LOW", "LULU", "LITE", "LYB", "MTB", "MPC", "MAR", "MRSH",
    "MLM", "MRVL", "MAS", "MA", "MKC", "MCD", "MCK", "MDT", "MRK", "META",
    "MET", "MTD", "MGM", "MCHP", "MU", "MSFT", "MAA", "MRNA", "TAP", "MDLZ",
    "MPWR", "MNST", "MCO", "MS", "MOS", "MSI", "MSCI", "NDAQ", "NTAP", "NFLX",
    "NEM", "NWSA", "NWS", "NEE", "NKE", "NI", "NDSN", "NSC", "NTRS", "NOC",
    "NCLH", "NRG", "NUE", "NVDA", "NVR", "NXPI", "ORLY", "OXY", "ODFL", "OMC",
    "ON", "OKE", "ORCL", "OTIS", "PCAR", "PKG", "PLTR", "PANW", "PSKY", "PH",
    "PAYX", "PYPL", "PNR", "PEP", "PFE", "PCG", "PM", "PSX", "PNW", "PNC",
    "PPG", "PPL", "PFG", "PG", "PGR", "PLD", "PRU", "PEG", "PTC", "PSA",
    "PHM", "PWR", "QCOM", "DGX", "Q", "RL", "RJF", "RTX", "O", "REG",
    "REGN", "RF", "RSG", "RMD", "RVTY", "HOOD", "ROK", "ROL", "ROP", "ROST",
    "RCL", "SPGI", "CRM", "SNDK", "SBAC", "SLB", "STX", "SRE", "NOW", "SHW",
    "SPG", "SWKS", "SJM", "SW", "SNA", "SOLV", "SO", "LUV", "SWK", "SBUX",
    "STT", "STLD", "STE", "SYK", "SMCI", "SYF", "SNPS", "SYY", "TMUS", "TROW",
    "TTWO", "TPR", "TRGP", "TGT", "TEL", "TDY", "TER", "TSLA", "TXN", "TPL",
    "TXT", "TMO", "TJX", "TKO", "TTD", "TSCO", "TT", "TDG", "TRV", "TRMB",
    "TFC", "TYL", "TSN", "USB", "UBER", "UDR", "ULTA", "UNP", "UAL", "UPS",
    "URI", "UNH", "UHS", "VLO", "VEEV", "VTR", "VLTO", "VRSN", "VRSK", "VZ",
    "VRTX", "VRT", "VTRS", "VICI", "V", "VST", "VMC", "WRB", "GWW", "WAB",
    "WMT", "DIS", "WBD", "WM", "WAT", "WEC", "WFC", "WELL", "WST", "WDC",
    "WY", "WSM", "WMB", "WTW", "WDAY", "WYNN", "XEL", "XYL", "YUM", "ZBRA",
    "ZBH", "ZTS",
]

# 미국 종목 해자(Moat) 정성 태그 [INPUT]  (없으면 'none' 으로 간주)
#   wide=강력한 독점적 해자 / narrow=일정 해자 / none=해자 약함
MOAT_TAGS = {
    "AAPL": "wide", "MSFT": "wide", "GOOGL": "wide", "META": "wide",
    "NVDA": "wide", "V": "wide", "MA": "wide", "ADBE": "wide",
    "ORCL": "narrow", "AVGO": "wide", "TXN": "wide", "QCOM": "narrow",
    "CSCO": "narrow", "INTC": "narrow", "IBM": "narrow",
    "KO": "wide", "PEP": "wide", "PG": "wide", "CL": "narrow",
    "MDLZ": "narrow", "MO": "wide", "PM": "wide", "HSY": "wide",
    "MCD": "wide", "SBUX": "narrow", "NKE": "wide", "DPZ": "narrow",
    "JNJ": "wide", "MRK": "narrow", "ABBV": "narrow", "AMGN": "narrow",
    "UNH": "wide", "GILD": "narrow",
    "HON": "narrow", "CAT": "narrow", "DE": "wide", "LMT": "wide",
    "NOC": "wide", "RTX": "narrow", "ITW": "wide", "GD": "narrow",
    "JPM": "narrow", "AXP": "wide", "BLK": "wide", "SPGI": "wide",
    "MCO": "wide",
    "XOM": "narrow", "CVX": "narrow",
    "WMT": "wide", "HD": "wide", "COST": "wide", "TJX": "wide", "LOW": "narrow",
    "DIS": "narrow", "CMCSA": "narrow",
    # S&P500 확대분 — 널리 인정되는 와이드/내로우 해자
    "MSCI": "wide", "ISRG": "wide", "INTU": "wide", "NOW": "wide", "CRM": "wide",
    "LLY": "wide", "ABT": "wide", "MDT": "narrow", "TMO": "wide", "DHR": "wide",
    "ACN": "narrow", "ADP": "wide", "PAYX": "wide", "FICO": "wide", "VRSN": "wide",
    "MCK": "narrow", "ELV": "narrow", "CI": "narrow", "HCA": "narrow",
    "UNP": "wide", "NSC": "wide", "CSX": "wide", "ODFL": "wide",
    "WM": "wide", "RSG": "wide", "TDG": "wide", "GE": "narrow", "ETN": "narrow",
    "KLAC": "wide", "LRCX": "wide", "AMAT": "wide", "SNPS": "wide",
    "CDNS": "wide", "ANET": "narrow", "NFLX": "narrow", "BKNG": "wide", "ABNB": "narrow",
    "CME": "wide", "ICE": "wide", "NDAQ": "wide", "SCHW": "narrow", "GS": "narrow",
    "MS": "narrow", "BRK-B": "wide", "AMZN": "wide", "ORLY": "wide", "AZO": "wide",
    "ULTA": "narrow", "CTAS": "wide", "WST": "narrow", "IDXX": "wide",
    "VRTX": "narrow", "REGN": "narrow", "BMY": "narrow", "PFE": "narrow",
    "KDP": "narrow", "MNST": "wide", "KMB": "narrow", "CLX": "narrow", "MKC": "wide",
    "SYK": "wide", "BSX": "narrow", "EW": "narrow", "ZTS": "wide", "WRB": "narrow",
}

# ──────────────────────────────────────────────────────────────────────────
# 4) 한국 워치리스트
#    [업데이트] 펀더멘털(FCF·부채·자본·EBITDA·EBIT·순이익·마진·ROE)은 이제
#    yfinance .KS(KOSPI)/.KQ(KOSDAQ) 로 *자동* 수집된다. 가격(LIVE)은 pykrx.
#    따라서 아래 dict 은 최소 정보만 둔다:
#      name      : 한글 종목명(표시용)
#      yf        : yfinance 티커 (KOSPI=코드.KS / KOSDAQ=코드.KQ)
#      moat_tag  : 해자 정성 태그 (wide / narrow / none)  [수동 판단]
#      (선택) shares / eps / bvps / fcf / total_debt / equity / ... :
#               yfinance 가 결측일 때만 쓰이는 *폴백* 수동값 (필요 시 입력).
#    → 미국과 동일하게 대부분 자동. moat_tag 만 사람이 판단해 갱신.
# ──────────────────────────────────────────────────────────────────────────
KR_WATCHLIST = {
    "005930": {"name": "삼성전자", "yf": "005930.KS", "moat_tag": "wide"},
    "000660": {"name": "SK하이닉스", "yf": "000660.KS", "moat_tag": "narrow"},
    "035420": {"name": "NAVER", "yf": "035420.KS", "moat_tag": "wide"},
    "012510": {"name": "더존비즈온", "yf": "012510.KQ", "moat_tag": "narrow",
               # KOSDAQ 은 yfinance 결측이 잦아 폴백값 보강
               "shares": 31_000_000, "eps": 1_400, "bvps": 16_000},
    "271560": {"name": "오리온", "yf": "271560.KS", "moat_tag": "wide"},
    "033780": {"name": "KT&G", "yf": "033780.KS", "moat_tag": "wide"},      # 담배 준독점 + 고FCF·저부채 (Dhandho 정석)
    "035250": {"name": "강원랜드", "yf": "035250.KS", "moat_tag": "wide"},   # 내국인 카지노 독점
    "030200": {"name": "KT", "yf": "030200.KS", "moat_tag": "narrow"},      # 통신 과점 + 안정 현금흐름
    "017670": {"name": "SK텔레콤", "yf": "017670.KS", "moat_tag": "narrow"},
    "316140": {"name": "우리금융지주", "yf": "316140.KS", "moat_tag": "narrow"},
}


# ──────────────────────────────────────────────────────────────────────────
# 평탄화 헬퍼
# ──────────────────────────────────────────────────────────────────────────
def all_us():
    """미국 유니버스 티커 리스트 반환."""
    return list(US_UNIVERSE)


def moat_tag_us(ticker: str) -> str:
    """미국 종목 해자 태그(없으면 none)."""
    return MOAT_TAGS.get(ticker, "none")


def all_kr():
    """(ticker, info) 리스트 반환."""
    return [(t, info) for t, info in KR_WATCHLIST.items()]
