# -*- coding: utf-8 -*-
"""UTM 파싱, 첫 유입 유지, Brevo 속성 변환."""
import unittest
from unittest import mock

import attribution
import brevo
import config
import waitlist


class ParseAndSanitizeTests(unittest.TestCase):
    def test_parses_standard_utm_keys(self):
        params = {
            "utm_source": " Naver ",
            "utm_medium": "cpc",
            "utm_campaign": "launch_2026",
            "utm_content": "hero",
            "utm_term": "가치투자",
            "unrelated": "ignore",
        }
        self.assertEqual(
            attribution.parse_utm_params(params),
            {
                "source": "Naver",
                "medium": "cpc",
                "campaign": "launch_2026",
                "content": "hero",
                "term": "가치투자",
            },
        )

    def test_query_param_list_uses_first_value(self):
        class _Params:
            def get_all(self, key):
                return ["first", "second"] if key == "utm_source" else []

            def get(self, key):
                raise AssertionError("get_all should win")

        self.assertEqual(attribution.parse_utm_params(_Params()), {"source": "first"})

    def test_strips_cookie_delimiters_and_truncates(self):
        raw = "a;b=c<d>" + ("x" * 200)
        cleaned = attribution.sanitize_utm_value(raw)
        self.assertNotIn(";", cleaned)
        self.assertNotIn("=", cleaned)
        self.assertNotIn("<", cleaned)
        self.assertLessEqual(len(cleaned), 100)

    def test_blank_and_none(self):
        self.assertEqual(attribution.sanitize_utm_value(None), "")
        self.assertEqual(attribution.sanitize_utm_value("   "), "")
        self.assertEqual(attribution.sanitize_utm_value(["", "kept"]), "")
        self.assertEqual(attribution.parse_utm_params({}), {})


class FirstTouchTests(unittest.TestCase):
    def test_keeps_stored_over_newer_campaign(self):
        stored = {"source": "newsletter", "medium": "email"}
        incoming = {"source": "twitter", "medium": "social", "campaign": "oct"}
        self.assertEqual(attribution.first_touch(stored, incoming), stored)

    def test_uses_incoming_when_nothing_stored(self):
        incoming = {"source": "google", "medium": "organic"}
        self.assertEqual(attribution.first_touch({}, incoming), incoming)
        self.assertEqual(attribution.first_touch(None, incoming), incoming)

    def test_cookie_not_loaded_does_not_persist_and_keeps_session(self):
        chosen, persist = attribution.resolve_attribution(
            {},
            {"source": "newsletter"},
            {"source": "twitter"},
            cookie_loaded=False,
        )
        self.assertEqual(chosen, {"source": "newsletter"})
        self.assertFalse(persist)

    def test_loaded_cookie_wins_over_session_and_url(self):
        chosen, persist = attribution.resolve_attribution(
            {"source": "newsletter", "medium": "email"},
            {"source": "twitter"},
            {"source": "google"},
            cookie_loaded=True,
        )
        self.assertEqual(chosen["source"], "newsletter")
        self.assertFalse(persist)

    def test_loaded_empty_cookie_persists_session_landing(self):
        chosen, persist = attribution.resolve_attribution(
            {},
            {"source": "naver", "medium": "cpc", "campaign": "oct"},
            {"source": "later"},
            cookie_loaded=True,
        )
        self.assertEqual(chosen["source"], "naver")
        self.assertTrue(persist)

    def test_direct_visit_is_not_persisted(self):
        chosen, persist = attribution.resolve_attribution(
            {}, {}, {}, cookie_loaded=True,
        )
        self.assertEqual(chosen, {})
        self.assertFalse(persist)

    def test_cookie_roundtrip_including_korean(self):
        original = {"source": "blog", "medium": "post", "campaign": "10월 캠페인", "term": "a&b"}
        decoded = attribution.decode_utm_cookie(attribution.encode_utm_cookie(original))
        self.assertEqual(decoded, original)

    def test_decode_json_and_dict(self):
        self.assertEqual(
            attribution.decode_utm_cookie('{"utm_source": "ig", "medium": "social"}'),
            {"source": "ig", "medium": "social"},
        )
        self.assertEqual(attribution.decode_utm_cookie(None), {})
        self.assertEqual(attribution.decode_utm_cookie("not-a-cookie"), {})


class BrevoAttributeTests(unittest.TestCase):
    def test_source_and_utm_attributes(self):
        attrs = attribution.brevo_signup_attributes(
            {"source": "naver", "medium": "cpc", "campaign": "launch", "content": "", "term": "가치"},
            joined_at="2026-10-30T00:00:00+00:00",
        )
        self.assertEqual(attrs["SOURCE"], "naver")
        self.assertEqual(attrs["UTM_SOURCE"], "naver")
        self.assertEqual(attrs["UTM_MEDIUM"], "cpc")
        self.assertEqual(attrs["UTM_CAMPAIGN"], "launch")
        self.assertEqual(attrs["UTM_TERM"], "가치")
        self.assertNotIn("UTM_CONTENT", attrs)
        self.assertEqual(attrs["JOINED_AT"], "2026-10-30T00:00:00+00:00")

    def test_missing_utm_is_direct_and_does_not_send_blank_utm(self):
        attrs = attribution.brevo_signup_attributes(None, joined_at="t")
        self.assertEqual(attrs["SOURCE"], "direct")
        self.assertNotIn("UTM_SOURCE", attrs)
        self.assertNotIn("UTM_MEDIUM", attrs)
        self.assertNotIn("UTM_CAMPAIGN", attrs)

    def test_medium_without_source_still_direct(self):
        attrs = attribution.brevo_signup_attributes({"medium": "email"}, joined_at="t")
        self.assertEqual(attrs["SOURCE"], "direct")
        self.assertEqual(attrs["UTM_MEDIUM"], "email")
        self.assertNotIn("UTM_SOURCE", attrs)

    def test_ensure_script_registers_utm_attributes(self):
        import importlib.util
        from pathlib import Path

        path = Path(__file__).resolve().parents[1] / "scripts" / "ensure_brevo_attributes.py"
        spec = importlib.util.spec_from_file_location("ensure_brevo_attributes", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for name in attribution.BREVO_UTM_ATTRIBUTES.values():
            self.assertEqual(mod.ATTRIBUTES[name], "text")
        self.assertEqual(mod.ATTRIBUTES["SOURCE"], "text")


class SignupSendTests(unittest.TestCase):
    def test_join_free_sends_channel_attributes(self):
        with mock.patch.object(config, "brevo_api_key", return_value="test-key"), \
             mock.patch.object(config, "brevo_free_list_id", return_value="11"), \
             mock.patch.object(brevo, "add_contact_to_list", return_value=True) as add:
            ok, code = waitlist.join_free(
                "Reader@Example.com",
                {"source": "naver", "medium": "cpc", "campaign": "launch"},
            )
        self.assertEqual((ok, code), (True, "success_free"))
        email, list_id, attrs, key = add.call_args[0]
        self.assertEqual(email, "reader@example.com")
        self.assertEqual(list_id, "11")
        self.assertEqual(key, "test-key")
        self.assertEqual(attrs["SOURCE"], "naver")
        self.assertEqual(attrs["UTM_SOURCE"], "naver")
        self.assertEqual(attrs["UTM_MEDIUM"], "cpc")
        self.assertEqual(attrs["UTM_CAMPAIGN"], "launch")
        self.assertIn("JOINED_AT", attrs)

    def test_join_free_without_utm_is_direct(self):
        with mock.patch.object(config, "brevo_api_key", return_value="k"), \
             mock.patch.object(config, "brevo_free_list_id", return_value="1"), \
             mock.patch.object(brevo, "add_contact_to_list", return_value=True) as add:
            ok, code = waitlist.join_free("a@b.co")
        self.assertEqual((ok, code), (True, "success_free"))
        attrs = add.call_args[0][2]
        self.assertEqual(attrs["SOURCE"], "direct")
        self.assertNotIn("UTM_SOURCE", attrs)

    def test_join_waitlist_blocked_when_promo_off(self):
        with mock.patch.object(config, "paid_promo_enabled", return_value=False), \
             mock.patch.object(brevo, "add_contact_to_list") as add:
            ok, code = waitlist.join_waitlist("a@b.co", {"source": "ig"})
        self.assertEqual((ok, code), (False, "promo_disabled"))
        add.assert_not_called()

    def test_join_waitlist_sends_utm_when_promo_on(self):
        with mock.patch.object(config, "paid_promo_enabled", return_value=True), \
             mock.patch.object(config, "brevo_api_key", return_value="k"), \
             mock.patch.object(config, "brevo_waitlist_list_id", return_value="9"), \
             mock.patch.object(brevo, "add_contact_to_list", return_value=True) as add:
            ok, code = waitlist.join_waitlist("a@b.co", {"source": "ig", "campaign": "early"})
        self.assertEqual((ok, code), (True, "success_waitlist"))
        attrs = add.call_args[0][2]
        self.assertEqual(attrs["SOURCE"], "ig")
        self.assertEqual(attrs["UTM_CAMPAIGN"], "early")
        self.assertIs(attrs["EARLYBIRD"], True)


if __name__ == "__main__":
    unittest.main()
