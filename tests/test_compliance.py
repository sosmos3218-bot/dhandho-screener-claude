# -*- coding: utf-8 -*-
"""동의, 통과 규칙, 뉴스레터 문구, 스킵 임계값, OTP."""
import datetime as dt
import unittest
from unittest import mock

import brevo
import config
import data
import newsletter
import otp_limit
import paid_gate
import privacy
import publish
import screening
import tier_display
import waitlist


def _raw(**overrides):
    base = {
        "ticker": "TEST", "name": "Test Co", "market": "US", "moat_tag": "none",
        "market_cap": 100.0, "fcf": 1.0, "total_debt": 10.0, "equity": 100.0,
        "ebit": 1.0, "ebitda": 10.0, "net_debt": 0.0, "enterprise_value": 100.0,
        "roic": 20.0, "gross_margin": 50.0, "pe": 10.0, "pb": 1.0,
        "earnings_yield": 1.0,
    }
    base.update(overrides)
    return base


class ConsentTests(unittest.TestCase):
    def test_join_free_requires_consent(self):
        with mock.patch.object(brevo, "add_contact_to_list") as add:
            ok, code = waitlist.join_free("a@b.co", {"source": "x"})
        self.assertEqual((ok, code), (False, "consent_required"))
        add.assert_not_called()

    def test_doi_used_when_template_and_redirect_set(self):
        with mock.patch.object(config, "brevo_api_key", return_value="k"), \
             mock.patch.object(config, "brevo_free_list_id", return_value="3"), \
             mock.patch.object(config, "brevo_doi_template_id", return_value="9"), \
             mock.patch.object(config, "brevo_doi_redirect_url", return_value="https://example.com/ok"), \
             mock.patch.object(brevo, "create_double_optin_contact", return_value=True) as doi, \
             mock.patch.object(brevo, "add_contact_to_list") as add:
            ok, code = waitlist.join_free("a@b.co", consent=True)
        self.assertEqual((ok, code), (True, "success_free"))
        doi.assert_called_once()
        add.assert_not_called()
        self.assertEqual(doi.call_args[0][3], "9")

    def test_template_without_redirect_stays_single_opt_in(self):
        with mock.patch.object(config, "brevo_api_key", return_value="k"), \
             mock.patch.object(config, "brevo_free_list_id", return_value="3"), \
             mock.patch.object(config, "brevo_doi_template_id", return_value="9"), \
             mock.patch.object(config, "brevo_doi_redirect_url", return_value=""), \
             mock.patch.object(brevo, "create_double_optin_contact") as doi, \
             mock.patch.object(brevo, "add_contact_to_list", return_value=True) as add:
            ok, code = waitlist.join_free("a@b.co", consent=True)
        self.assertEqual((ok, code), (True, "success_free"))
        doi.assert_not_called()
        add.assert_called_once()

    def test_admin_notice_escapes_html(self):
        with mock.patch.object(config, "brevo_api_key", return_value="k"), \
             mock.patch.object(config, "brevo_sender", return_value=("ops@example.com", "Ops")), \
             mock.patch.object(brevo, "send_transactional_email", return_value=True) as send:
            waitlist._notify_admin_ticker_request("a<b>@c.com", "<IMG SRC=X>")
        html = send.call_args[0][4]
        self.assertNotIn("<IMG", html)
        self.assertIn("&lt;IMG SRC=X&gt;", html)
        self.assertIn("a&lt;b&gt;@c.com", html)

    def test_privacy_draft_has_required_points(self):
        text = privacy.markdown("ko")
        for phrase in ("초안", "변호사", "뉴스레터", "이메일", "Brevo", "구독", "[담당자 이메일]", privacy.POLICY_VERSION):
            self.assertIn(phrase, text)
        self.assertNotIn("·", text)
        self.assertNotIn("—", text)


class ScreenRuleTests(unittest.TestCase):
    def test_negative_pe_does_not_count_as_cheap(self):
        # 현금흐름 실패, 부채 통과, ROIC 통과. 가치 축은 P/E 에만 기대고 이익수익률은 낮다.
        blocked = screening.build_row(_raw(fcf=1.0, pe=-5.0, earnings_yield=1.0, roic=20.0))
        allowed = screening.build_row(_raw(fcf=1.0, pe=10.0, earnings_yield=1.0, roic=20.0))
        self.assertFalse(blocked["passes"])
        self.assertTrue(allowed["passes"])
        self.assertLess(blocked["score_value"], allowed["score_value"])

    def test_wide_moat_tag_does_not_bypass_roic(self):
        row = screening.build_row(_raw(roic=1.0, moat_tag="wide", pe=10.0, fcf=20.0))
        self.assertNotIn("🏰해자", row["flags"])
        # 현금흐름, 부채, 가치는 통과할 수 있지만 해자 축은 ROIC 미달이라 3축이 안 된다.
        # fcf 20 / mc 100 = 20% 통과, pe 10 통과, roic 1 실패. 부채 통과. 합계 3.
        # 가치+현금+부채 = 3 이라 통과할 수 있다. 해자 플래그만 막히는지가 핵심이다.
        self.assertGreater(row["score_moat"], 0)  # 태그 보너스는 점수에 남는다

    def test_wide_tag_still_adds_score_bonus(self):
        plain = screening.build_row(_raw(roic=20.0, moat_tag="none"))
        wide = screening.build_row(_raw(roic=20.0, moat_tag="wide"))
        self.assertGreater(wide["score_moat"], plain["score_moat"])


class KrFallbackTests(unittest.TestCase):
    def test_manual_fcf_used_when_yfinance_fails(self):
        failed = {
            "error": "info 실패: boom", "market_cap": None, "fcf": None, "price": None,
            "total_debt": None, "equity": None, "ebit": None, "ebitda": None,
            "shares": None, "net_income": None, "invested_capital": None, "roe": None,
            "gross_margin": None, "op_margin_std": None, "total_cash": None,
        }
        info = {"name": "삼성전자", "fcf": 123.0, "moat_tag": "none", "shares": 10}
        with mock.patch.object(data, "_yf_raw", return_value=failed), \
             mock.patch.object(data, "_kr_latest_close", return_value=(None, None)), \
             mock.patch.object(data.time, "sleep"):
            row = data.fetch_kr("005930", info, use_cache=False)
        self.assertEqual(row["name"], "삼성전자")
        self.assertEqual(row["fcf"], 123.0)
        self.assertEqual(row["error"], "info 실패: boom")


class PipelineTests(unittest.TestCase):
    def test_skip_threshold_per_market(self):
        stats = {
            "US": {"attempted": 100, "skipped": 11},
            "KR": {"attempted": 10, "skipped": 1},
            "JP": {"attempted": 0, "skipped": 0},
        }
        self.assertEqual(screening.markets_over_skip_threshold(stats, 0.10), ["US"])
        self.assertEqual(screening.markets_over_skip_threshold(stats, 0.20), [])

    def test_stale_after_eight_days(self):
        now = dt.datetime(2026, 10, 30, 12, 0, 0)
        self.assertFalse(publish.is_stale("2026-10-26T01:01:31", now=now))
        self.assertTrue(publish.is_stale("2026-10-20T01:01:31", now=now))
        self.assertTrue(publish.is_stale("", now=now))

    def test_tax_rates(self):
        self.assertEqual(config.tax_rate("US"), 0.21)
        self.assertEqual(config.tax_rate("KR"), 0.242)
        self.assertEqual(config.tax_rate("JP"), 0.306)
        self.assertEqual(config.tax_rate("XX"), 0.21)


class NewsletterCopyTests(unittest.TestCase):
    def _latest(self):
        row = {
            "ticker": "AAA", "name": "Alpha", "market": "US", "dhandho_score": 80,
            "fcf_yield": 10, "debt_equity": 0.2, "roic": 18, "pe": 12, "moat_tag": "none",
        }
        return {
            "date": "2026-10-26", "n_pass": 1, "total_scanned": 10,
            "passes": [row],
        }

    def test_market_comment_is_factual(self):
        head, body = newsletter.market_comment(2, 100)
        blob = head + body
        for banned in ("현금", "담을 기회", "인내", "매수", "헐값"):
            self.assertNotIn(banned, blob)
        self.assertIn(newsletter.LIST_DISCLAIMER and "통과", blob)

    def test_free_edition_hides_paid_teaser_when_flag_off(self):
        with mock.patch.object(config, "paid_promo_enabled", return_value=False):
            md = newsletter.build_markdown(self._latest(), None, tier="free")
            subject = newsletter.edition_subject("2026-10-26", "free", 1)
        self.assertIn("Alpha", md)
        self.assertIn(newsletter.LIST_DISCLAIMER, md)
        self.assertNotIn("유료판에서", md)
        self.assertNotIn("(광고)", subject)
        self.assertNotIn("헐값", md)

    def test_ad_prefix_only_when_promo_on(self):
        with mock.patch.object(config, "paid_promo_enabled", return_value=True):
            subject = newsletter.edition_subject("2026-10-26", "paid", 1)
            md = newsletter.build_markdown(self._latest(), None, tier="free")
        self.assertTrue(subject.startswith("(광고)"))
        self.assertIn("유료판에서", md)

    def test_full_list_flag(self):
        self.assertTrue(tier_display.shows_full_public_list(False, False))
        self.assertFalse(tier_display.shows_full_public_list(True, False))
        self.assertTrue(tier_display.shows_full_public_list(True, True))
        self.assertEqual(
            tier_display.LIST_DISCLAIMER_KO,
            "사전에 정한 조건을 통과한 목록이며 투자 권유가 아닙니다.",
        )


class OtpTests(unittest.TestCase):
    def test_rate_limit_persists(self):
        import tempfile
        from pathlib import Path
        path = Path(tempfile.mkdtemp()) / "otp.json"
        now = dt.datetime(2026, 10, 30, tzinfo=dt.timezone.utc)
        self.assertTrue(otp_limit.check_and_mark("a@b.co", now=now, path=path, cooldown_sec=60))
        later = now + dt.timedelta(seconds=10)
        self.assertFalse(otp_limit.check_and_mark("a@b.co", now=later, path=path, cooldown_sec=60))
        after = now + dt.timedelta(seconds=61)
        self.assertTrue(otp_limit.check_and_mark("a@b.co", now=after, path=path, cooldown_sec=60))

    def test_not_paid_does_not_reveal_membership(self):
        with mock.patch.object(otp_limit, "check_and_mark", return_value=True), \
             mock.patch.object(paid_gate, "is_paid_email", return_value=False), \
             mock.patch.object(brevo, "send_transactional_email") as send:
            ok, result = paid_gate.send_login_otp("reader@example.com")
        self.assertTrue(ok)
        self.assertIsNone(result)
        send.assert_not_called()

    def test_otp_compare_uses_digest(self):
        state = {
            "email": "a@b.co",
            "code": "123456",
            "expires": (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5)).isoformat(),
        }
        self.assertTrue(paid_gate.verify_login_otp(state, "a@b.co", "123456"))
        self.assertFalse(paid_gate.verify_login_otp(state, "a@b.co", "123457"))
        self.assertFalse(paid_gate.verify_login_otp(state, "a@b.co", "12345"))


if __name__ == "__main__":
    unittest.main()
