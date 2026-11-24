# -*- coding: utf-8 -*-
"""KST 날짜 라벨과 is_stale. 레거시 naive 타임스탬프는 UTC 로 본다."""
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import clock
import data
import publish

KST = ZoneInfo("Asia/Seoul")


class ClockTests(unittest.TestCase):
    def test_sunday_2300_utc_is_monday_in_kst(self):
        # cron 0 23 * * 0 UTC = 월요일 08:00 KST
        moment = datetime(2026, 11, 1, 23, 0, tzinfo=timezone.utc)
        self.assertEqual(clock.kst_date_label(moment), "2026-11-02")
        self.assertEqual(clock.iso_kst(moment), "2026-11-02T08:00:00+09:00")

    def test_kst_monday_morning_stays_monday(self):
        moment = datetime(2026, 11, 2, 8, 5, tzinfo=KST)
        self.assertEqual(clock.kst_date_label(moment), "2026-11-02")
        self.assertTrue(clock.iso_kst(moment).endswith("+09:00"))


class IsStaleTests(unittest.TestCase):
    def test_legacy_naive_is_utc(self):
        # 2026-10-26 01:01 UTC 를 한국 11월 2일 08:00 과 비교하면 8일 미만.
        now = datetime(2026, 11, 2, 8, 0, tzinfo=KST)
        self.assertFalse(publish.is_stale("2026-10-26T01:01:31", now=now))
        self.assertTrue(publish.is_stale("2026-10-20T01:01:31", now=now))

    def test_aware_kst_and_z_suffix(self):
        now = datetime(2026, 11, 2, 9, 0, tzinfo=KST)
        self.assertFalse(publish.is_stale("2026-11-02T08:00:00+09:00", now=now))
        self.assertTrue(publish.is_stale("2026-10-01T00:00:00Z", now=now))
        self.assertTrue(publish.is_stale("not-a-date", now=now))

    def test_naive_now_is_treated_as_utc(self):
        now = datetime(2026, 10, 30, 12, 0, 0)
        self.assertFalse(publish.is_stale("2026-10-26T01:01:31", now=now))
        self.assertTrue(publish.is_stale("2026-10-20T01:01:31", now=now))
        self.assertTrue(publish.is_stale("", now=now))


class RunCacheTests(unittest.TestCase):
    def test_second_fetch_reuses_success_without_refetch(self):
        tmp = tempfile.mkdtemp()
        calls = {"n": 0}

        def fake_raw(ticker, market):
            calls["n"] += 1
            return {"ticker": ticker, "market": market, "market_cap": 1, "error": None}

        env = {"DHANDHO_RUN_CACHE": "1", "DHANDHO_CACHE_DIR": tmp}
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(data, "_yf_raw", side_effect=fake_raw), \
             mock.patch.object(data.time, "sleep"):
            first = data.fetch_us("AAPL", use_cache=False)
            second = data.fetch_us("AAPL", use_cache=False)
        self.assertEqual(calls["n"], 1)
        self.assertEqual(first["market_cap"], second["market_cap"])
        self.assertTrue(list(Path(tmp).glob("run/*/*.json")))

    def test_error_is_not_cached(self):
        tmp = tempfile.mkdtemp()
        calls = {"n": 0}

        def fake_raw(ticker, market):
            calls["n"] += 1
            if calls["n"] == 1:
                return {"ticker": ticker, "error": "boom", "market_cap": None}
            return {"ticker": ticker, "market": market, "market_cap": 2, "error": None}

        env = {"DHANDHO_RUN_CACHE": "1", "DHANDHO_CACHE_DIR": tmp}
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(data, "_yf_raw", side_effect=fake_raw), \
             mock.patch.object(data.time, "sleep"):
            data.fetch_us("MSFT", use_cache=False)
            data.fetch_us("MSFT", use_cache=False)
        self.assertEqual(calls["n"], 2)


class AtomicWriteTests(unittest.TestCase):
    def test_concurrent_writes_stay_valid_json(self):
        import json
        import threading
        import atomic_io
        path = Path(tempfile.mkdtemp()) / "otp.json"
        errors = []

        def write(i):
            try:
                atomic_io.atomic_write_text(path, json.dumps({"i": i, "pad": "x" * 200}))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=write, args=(i,)) for i in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        loaded = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("i", loaded)
        self.assertLess(loaded["i"], 12)


if __name__ == "__main__":
    unittest.main()
