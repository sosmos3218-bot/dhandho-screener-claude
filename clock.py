# -*- coding: utf-8 -*-
"""한국 표준시(Asia/Seoul) 기준 시각.

주간 잡은 UTC 일요일 23:00에 시작하지만, 그 시각은 한국 월요일 08:00이다.
파일 이름과 generated_at 은 그 월요일 날짜를 써야 한다.
저장 형식은 오프셋이 붙은 ISO8601 (+09:00).
과거에 저장된 타임존 없는 문자열은 UTC 로 해석한 뒤 비교한다.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def now_kst() -> datetime:
    return datetime.now(KST)


def today_kst():
    return now_kst().date()


def as_aware(moment: datetime) -> datetime:
    """naive 값은 UTC 로 둔다. aware 값은 그대로 둔다."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


def parse_timestamp(text: str) -> datetime:
    """ISO 문자열을 aware datetime 으로. Z 와 레거시 naive(UTC 취급)를 받는다."""
    stamp = datetime.fromisoformat(str(text).strip().replace("Z", "+00:00"))
    return as_aware(stamp)


def iso_kst(moment: datetime = None) -> str:
    """+09:00 오프셋이 붙은 ISO8601."""
    moment = now_kst() if moment is None else as_aware(moment)
    return moment.astimezone(KST).isoformat(timespec="seconds")


def kst_date_label(moment: datetime = None) -> str:
    """스냅샷 파일 이름에 쓰는 YYYY-MM-DD. 기준은 한국 달력."""
    moment = now_kst() if moment is None else as_aware(moment)
    return moment.astimezone(KST).date().isoformat()
