# -*- coding: utf-8 -*-
"""유료 홍보 문구: 평생 할인 제거, 기간 한정, 기본은 숨김."""
import ast
import os
import unittest
from pathlib import Path
from unittest import mock

import config

ROOT = Path(__file__).resolve().parents[1]

_BANNED = (
    "평생 할인",
    "평생 할인가",
    "for life",
    "lifetime discount",
    "永久割引",
)


def _i18n_strings() -> dict:
    tree = ast.parse((ROOT / "i18n.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "_S" for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("i18n._S not found")


class PromoFlagTests(unittest.TestCase):
    def test_default_off_without_env_or_secrets(self):
        env = {k: v for k, v in os.environ.items() if k != "PAID_PROMO_ENABLED"}
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch.object(config, "_load_secrets", return_value={}):
            self.assertFalse(config.paid_promo_enabled())

    def test_env_on_values(self):
        for raw in ("1", "true", "TRUE", "yes", "on"):
            with mock.patch.dict(os.environ, {"PAID_PROMO_ENABLED": raw}, clear=False), \
                 mock.patch.object(config, "_load_secrets", return_value={}):
                self.assertTrue(config.paid_promo_enabled(), raw)

    def test_env_off_beats_secrets_true(self):
        # 환경변수가 비어 있을 때만 secrets 를 본다. 명시적 false 는 끈다.
        with mock.patch.dict(os.environ, {"PAID_PROMO_ENABLED": "false"}, clear=False), \
             mock.patch.object(config, "_load_secrets", return_value={"paid_promo_enabled": True}):
            self.assertFalse(config.paid_promo_enabled())

    def test_secrets_boolean_true_when_env_unset(self):
        env = {k: v for k, v in os.environ.items() if k != "PAID_PROMO_ENABLED"}
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch.object(config, "_load_secrets", return_value={"paid_promo_enabled": True}):
            self.assertTrue(config.paid_promo_enabled())

    def test_deadline_placeholder_and_override(self):
        env = {k: v for k, v in os.environ.items() if k != "EARLYBIRD_DEADLINE"}
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch.object(config, "_load_secrets", return_value={}):
            self.assertEqual(config.earlybird_deadline(), "YYYY-MM-DD")
        with mock.patch.dict(os.environ, {"EARLYBIRD_DEADLINE": "2026-12-31"}, clear=False):
            self.assertEqual(config.earlybird_deadline(), "2026-12-31")


class CopyTests(unittest.TestCase):
    def test_lifetime_offer_removed_from_user_facing_files(self):
        files = [
            "i18n.py",
            "README.md",
            "app.py",
            "waitlist.py",
            "secrets.example.json",
            "newsletter.py",
        ]
        for name in files:
            text = (ROOT / name).read_text(encoding="utf-8")
            for phrase in _BANNED:
                self.assertNotIn(phrase, text, f"{phrase} still in {name}")

    def test_paid_promo_copy_is_time_limited(self):
        strings = _i18n_strings()
        self.assertNotIn("signup_body", strings)
        paid = strings["signup_body_paid"]
        success = strings["msg_success_waitlist"]
        self.assertIn("{deadline}", paid["ko"])
        self.assertIn("첫 12개월 50% 할인", paid["ko"])
        self.assertIn("가입자 한정", paid["ko"])
        self.assertIn("{deadline}", success["ko"])
        self.assertIn("first 12 months", paid["en"])
        self.assertIn("12ヶ月", paid["ja"])
        self.assertIn("{deadline}", paid["en"])
        self.assertIn("{deadline}", paid["ja"])

    def test_new_korean_copy_has_no_middle_dot_or_em_dash(self):
        strings = _i18n_strings()
        keys = (
            "signup_body_free",
            "signup_body_paid",
            "msg_success_waitlist",
            "msg_promo_disabled",
        )
        for key in keys:
            korean = strings[key]["ko"]
            self.assertNotIn("·", korean, key)
            self.assertNotIn("—", korean, key)
            self.assertNotIn("평생", korean, key)


if __name__ == "__main__":
    unittest.main()
