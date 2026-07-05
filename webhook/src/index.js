// Dhandho Screener — 결제 웹훅 Provider Adapter (Cloudflare Worker)
//
// 흐름:
//   구매자가 Polar/Stripe 결제 완료
//     → 각 PG가 전용 엔드포인트로 웹훅 발송
//     → 서명 검증 후 구매자 이메일을 Brevo 유료 리스트(BREVO_PAID_LIST_ID)에 추가/제거
//     → dhandho-screener 대시보드/뉴스레터가 그 리스트를 조회해 유료 여부 판단
//
// 엔드포인트:
//   POST /stripe-webhook  — Stripe checkout.session.completed
//   POST /webhook/polar   — Polar order.paid / subscription.active / subscription.revoked
//
// 시크릿 (`npx wrangler secret put <이름>`):
//   BREVO_API_KEY, BREVO_PAID_LIST_ID  — 필수
//   STRIPE_WEBHOOK_SECRET              — Stripe 사용 시
//   POLAR_WEBHOOK_SECRET               — Polar 사용 시 (whsec_...)

const BREVO_CONTACTS = "https://api.brevo.com/v3/contacts";
const REPLAY_TOLERANCE_SECONDS = 5 * 60;
const IDEMPOTENCY_TTL_SECONDS = 60 * 60 * 24 * 7; // Polar 재시도(최대 ~75h) 대비

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

function empty(status = 202) {
  return new Response("", { status, headers: { "Cache-Control": "no-store" } });
}

function toHex(buffer) {
  return Array.from(new Uint8Array(buffer)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

function constantTimeEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function decodeBase64Secret(secret) {
  const raw = secret.startsWith("whsec_") ? secret.slice(6) : secret;
  const binary = atob(raw);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

async function verifyStripeSignature(rawBody, sigHeader, secret) {
  if (!sigHeader) return false;
  const parts = Object.fromEntries(
    sigHeader.split(",").map((kv) => {
      const [k, v] = kv.split("=");
      return [k, v];
    })
  );
  const timestamp = parts.t;
  const signature = parts.v1;
  if (!timestamp || !signature) return false;

  const age = Math.abs(Date.now() / 1000 - Number(timestamp));
  if (!Number.isFinite(age) || age > REPLAY_TOLERANCE_SECONDS) return false;

  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const expectedSig = toHex(
    await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(`${timestamp}.${rawBody}`))
  );
  return expectedSig === signature;
}

async function verifyPolarSignature(rawBody, headers, secret) {
  const webhookId = headers.get("webhook-id");
  const timestamp = headers.get("webhook-timestamp");
  const signatureHeader = headers.get("webhook-signature");
  if (!webhookId || !timestamp || !signatureHeader) return false;

  const age = Math.abs(Date.now() / 1000 - Number(timestamp));
  if (!Number.isFinite(age) || age > REPLAY_TOLERANCE_SECONDS) return false;

  const key = await crypto.subtle.importKey(
    "raw",
    decodeBase64Secret(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const signed = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(`${webhookId}.${timestamp}.${rawBody}`)
  );
  const expectedB64 = btoa(String.fromCharCode(...new Uint8Array(signed)));

  for (const part of signatureHeader.split(" ")) {
    const [version, sig] = part.split(",");
    if (version === "v1" && sig && constantTimeEqual(sig, expectedB64)) return true;
  }
  return false;
}

async function isDuplicateWebhook(env, idempotencyKey) {
  if (!env.WEBHOOK_IDEMPOTENCY || !idempotencyKey) return false;
  const existing = await env.WEBHOOK_IDEMPOTENCY.get(`processed:${idempotencyKey}`);
  return Boolean(existing);
}

async function markWebhookProcessed(env, idempotencyKey) {
  if (!env.WEBHOOK_IDEMPOTENCY || !idempotencyKey) return;
  await env.WEBHOOK_IDEMPOTENCY.put(`processed:${idempotencyKey}`, "1", {
    expirationTtl: IDEMPOTENCY_TTL_SECONDS,
  });
}

async function addPaidContact(env, email, attributes) {
  const key = env.BREVO_API_KEY;
  const listId = parseInt(env.BREVO_PAID_LIST_ID, 10);
  if (!key || !listId) {
    return { ok: false, error: "server_misconfigured" };
  }
  const r = await fetch(BREVO_CONTACTS, {
    method: "POST",
    headers: { accept: "application/json", "content-type": "application/json", "api-key": key },
    body: JSON.stringify({ email, listIds: [listId], updateEnabled: true, attributes }),
  });
  return { ok: r.status === 201 || r.status === 204, status: r.status };
}

async function removePaidContact(env, email) {
  const key = env.BREVO_API_KEY;
  const listId = parseInt(env.BREVO_PAID_LIST_ID, 10);
  if (!key || !listId) {
    return { ok: false, error: "server_misconfigured" };
  }
  const r = await fetch(`${BREVO_CONTACTS}/lists/${listId}/contacts/remove`, {
    method: "POST",
    headers: { accept: "application/json", "content-type": "application/json", "api-key": key },
    body: JSON.stringify({ emails: [email] }),
  });
  // 201 = removed; 404 = contact not on list (idempotent revoke)
  return { ok: r.status === 201 || r.status === 404, status: r.status };
}

function extractPolarEmail(data) {
  return String(data?.customer?.email || data?.email || "")
    .trim()
    .toLowerCase();
}

async function handleStripeWebhook(request, env) {
  if (request.method !== "POST") {
    return json({ ok: false, error: "method_not_allowed" }, 405);
  }
  if (!env.STRIPE_WEBHOOK_SECRET || !env.BREVO_API_KEY || !env.BREVO_PAID_LIST_ID) {
    return json({ ok: false, error: "server_misconfigured" }, 500);
  }

  const rawBody = await request.text();
  const validSig = await verifyStripeSignature(rawBody, request.headers.get("Stripe-Signature"), env.STRIPE_WEBHOOK_SECRET);
  if (!validSig) {
    return json({ ok: false, error: "invalid_signature" }, 400);
  }

  let event;
  try {
    event = JSON.parse(rawBody);
  } catch {
    return json({ ok: false, error: "invalid_json" }, 400);
  }

  if (event.type !== "checkout.session.completed") {
    return json({ ok: true, ignored: event.type });
  }

  const idempotencyKey = `stripe:${event.id || request.headers.get("webhook-id") || ""}`;
  if (idempotencyKey !== "stripe:" && (await isDuplicateWebhook(env, idempotencyKey))) {
    return json({ ok: true, duplicate: true });
  }

  const session = event.data?.object || {};
  const email = (session.customer_details?.email || session.customer_email || "").trim().toLowerCase();
  if (!email) {
    return json({ ok: false, error: "no_email_in_session" }, 200);
  }

  const result = await addPaidContact(env, email, {
    SOURCE: "dhandho-screener stripe webhook",
    STRIPE_SESSION: session.id || "",
    PAID_AT: new Date().toISOString(),
  });
  if (!result.ok) {
    return json({ ok: false, error: "brevo_error", status: result.status }, 502);
  }

  if (idempotencyKey !== "stripe:") await markWebhookProcessed(env, idempotencyKey);
  return json({ ok: true });
}

async function handlePolarWebhook(request, env) {
  if (request.method !== "POST") {
    return json({ ok: false, error: "method_not_allowed" }, 405);
  }
  if (!env.POLAR_WEBHOOK_SECRET || !env.BREVO_API_KEY || !env.BREVO_PAID_LIST_ID) {
    return json({ ok: false, error: "server_misconfigured" }, 500);
  }

  const rawBody = await request.text();
  const webhookId = request.headers.get("webhook-id") || "";
  const validSig = await verifyPolarSignature(rawBody, request.headers, env.POLAR_WEBHOOK_SECRET);
  if (!validSig) {
    return json({ ok: false, error: "invalid_signature" }, 403);
  }

  let event;
  try {
    event = JSON.parse(rawBody);
  } catch {
    return json({ ok: false, error: "invalid_json" }, 400);
  }

  const eventType = event.type || "";
  const data = event.data || {};

  const grantEvents = new Set(["order.paid", "subscription.active"]);
  const revokeEvents = new Set(["subscription.revoked"]);

  if (!grantEvents.has(eventType) && !revokeEvents.has(eventType)) {
    return empty(202);
  }

  if (webhookId && (await isDuplicateWebhook(env, webhookId))) {
    return empty(202);
  }

  const email = extractPolarEmail(data);
  if (!email) {
    return empty(202);
  }

  if (eventType === "order.paid" && data.paid === false) {
    return empty(202);
  }

  let result;
  if (revokeEvents.has(eventType)) {
    result = await removePaidContact(env, email);
  } else {
    result = await addPaidContact(env, email, {
      SOURCE: "dhandho-screener polar webhook",
      POLAR_EVENT: eventType,
      POLAR_ORDER: data.id || "",
      POLAR_SUBSCRIPTION: data.subscription_id || data.id || "",
      PAID_AT: new Date().toISOString(),
    });
  }

  if (!result.ok) {
    return json({ ok: false, error: "brevo_error", status: result.status }, 502);
  }

  if (webhookId) await markWebhookProcessed(env, webhookId);
  return empty(202);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/stripe-webhook") {
      return handleStripeWebhook(request, env);
    }
    if (url.pathname === "/webhook/polar") {
      return handlePolarWebhook(request, env);
    }
    if (url.pathname === "/" || url.pathname === "/health") {
      return json({
        ok: true,
        service: "dhandho-screener-webhook",
        providers: { stripe: "/stripe-webhook", polar: "/webhook/polar" },
      });
    }
    return json({ ok: false, error: "not_found" }, 404);
  },
};