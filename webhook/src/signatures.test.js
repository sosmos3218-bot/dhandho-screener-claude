import assert from "node:assert/strict";
import test from "node:test";

import {
  constantTimeEqual,
  verifyPolarSignature,
  verifyStripeSignature,
} from "./index.js";

test("constantTimeEqual rejects different lengths and values", () => {
  assert.equal(constantTimeEqual("abcd", "abcd"), true);
  assert.equal(constantTimeEqual("abcd", "abce"), false);
  assert.equal(constantTimeEqual("abcd", "abc"), false);
});

test("stripe signature accepts a fresh hmac and rejects a bad one", async () => {
  const secret = "whsec_test_secret";
  const body = JSON.stringify({ id: "evt_1", type: "checkout.session.completed" });
  const timestamp = String(Math.floor(Date.now() / 1000));
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const mac = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(`${timestamp}.${body}`),
  );
  const hex = Array.from(new Uint8Array(mac)).map((b) => b.toString(16).padStart(2, "0")).join("");
  assert.equal(await verifyStripeSignature(body, `t=${timestamp},v1=${hex}`, secret), true);
  assert.equal(await verifyStripeSignature(body, `t=${timestamp},v1=${"0".repeat(hex.length)}`, secret), false);
  assert.equal(await verifyStripeSignature(body, "", secret), false);
});

test("polar signature accepts a fresh v1 signature", async () => {
  const secret = "whsec_" + Buffer.from("polar-test-secret").toString("base64");
  const body = JSON.stringify({ type: "order.paid" });
  const webhookId = "msg_1";
  const timestamp = String(Math.floor(Date.now() / 1000));
  const raw = secret.startsWith("whsec_") ? secret.slice(6) : secret;
  const key = await crypto.subtle.importKey(
    "raw",
    Buffer.from(raw, "base64"),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const mac = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(`${webhookId}.${timestamp}.${body}`),
  );
  const b64 = Buffer.from(mac).toString("base64");
  const headers = new Headers({
    "webhook-id": webhookId,
    "webhook-timestamp": timestamp,
    "webhook-signature": `v1,${b64}`,
  });
  assert.equal(await verifyPolarSignature(body, headers, secret), true);
  headers.set("webhook-signature", "v1,aaaa");
  assert.equal(await verifyPolarSignature(body, headers, secret), false);
});
