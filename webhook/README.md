# Dhandho Screener 결제 웹훅 (Polar / Stripe → Brevo)

결제 완료·갱신 시 구매자 이메일을 Brevo "유료" 리스트에 자동 추가하고, 구독 해지 시 제거하는 Cloudflare Worker.
`dhandho-screener`의 대시보드(`app.py`)와 뉴스레터(`newsletter.py`)는 이 리스트를 조회해
유료 여부를 판단하므로, `secrets.json`을 구독자마다 수동으로 고칠 필요가 없다.

## 아키텍처 (Provider Adapter)

| 엔드포인트 | PG | 처리 이벤트 | Brevo 동작 |
|-----------|-----|------------|-----------|
| `POST /webhook/polar` | **Polar** (권장) | `order.paid`, `subscription.active` | 유료 리스트 추가 |
| `POST /webhook/polar` | Polar | `subscription.revoked` | 유료 리스트 제거 |
| `POST /stripe-webhook` | Stripe (선택) | `checkout.session.completed` | 유료 리스트 추가 |

Polar 이벤트 매핑 (Stripe 대응):

| Stripe | Polar | 비고 |
|--------|-------|------|
| `checkout.session.completed` (최초 결제) | `order.paid` (`billing_reason: subscription_create`) | |
| (갱신) | `order.paid` (`billing_reason: subscription_cycle`) | 동일 핸들러 |
| — | `subscription.active` | 보조 확인용 |
| — | `subscription.revoked` | 즉시 해지·만료 시 접근 제거 |
| — | `subscription.canceled` | **무시** (기간 종료까지 유료 유지, `revoked` 대기) |

## 1. Brevo — 유료 전용 리스트

기존 dhandho-weekly/dhandho-landing 에서 쓰던 Brevo **계정/API 키는 그대로 재사용**하고,
dhandho-screener 전용으로 새 리스트만 하나 만든다.

1. Brevo 대시보드 → Contacts → Lists → **Create a list** (예: "Dhandho Screener - Paid")
2. 생성된 리스트의 ID 확인
3. Settings → SMTP & API → API Keys 에서 기존 키 재확인

## 2. Polar — 상품 + 웹훅 (권장, 무사업자 + 한국 정산)

1. [polar.sh](https://polar.sh) 에서 Organization 생성 → KYC/정산(Stripe Connect Express, KR 지원) 완료
2. **Products** → 구독 상품 생성 → **Checkout Link** 복사 (사이트/Streamlit에 링크 게시)
3. Organization Settings → **Webhooks** → **Add Endpoint**
   - URL: `https://dhandho-screener-webhook.dhandho.workers.dev/webhook/polar`
   - Format: **Raw** (JSON)
   - Secret: 생성된 `whsec_...` 복사
   - 구독 이벤트:
     - `order.paid`
     - `subscription.active`
     - `subscription.revoked`
4. 로컬 테스트: [Polar CLI](https://polar.sh/docs/integrate/webhooks/endpoints) `polar listen http://localhost:8787/webhook/polar`

## 3. Stripe — Payment Link + Webhook (선택, 사업자/해외 계정 필요 시)

1. Stripe 대시보드 → Payment Links → **Payment Link 생성**
2. Developers → Webhooks → **Add endpoint**
   - URL: `https://<Worker URL>/stripe-webhook`
   - 이벤트: `checkout.session.completed`
3. Signing secret (`whsec_...`) 복사

## 4. Worker 배포

```bash
cd dhandho-screener/webhook
npm install
npx wrangler login

# 필수
npx wrangler secret put BREVO_API_KEY
npx wrangler secret put BREVO_PAID_LIST_ID

# Polar 사용 시
npx wrangler secret put POLAR_WEBHOOK_SECRET

# Stripe 사용 시 (선택)
npx wrangler secret put STRIPE_WEBHOOK_SECRET

# (권장) 멱등성 KV — webhook-id 중복 처리 방지
npx wrangler kv namespace create WEBHOOK_IDEMPOTENCY
# wrangler.toml 의 kv_namespaces id 를 채운 뒤:

npx wrangler deploy
```

배포 URL: `https://dhandho-screener-webhook.dhandho.workers.dev`

## 5. dhandho-screener 쪽 설정

`dhandho-screener/secrets.json` (`secrets.example.json` 참고):

```json
{
  "brevo_api_key": "Brevo API 키",
  "brevo_paid_list_id": "유료 리스트 ID",
  "brevo_sender_email": "발신자 이메일",
  "brevo_sender_name": "발신자 이름"
}
```

클라우드 배포(Streamlit / HF Spaces)에는 `BREVO_API_KEY`, `BREVO_PAID_LIST_ID` 환경변수로 등록.

## 6. 동작 확인

**Polar (Sandbox 권장)**

1. Polar Sandbox에서 테스트 구독 결제
2. Polar Webhooks → Deliveries 에서 `202` 응답 확인
3. Brevo 리스트에 이메일 추가 확인
4. dhandho-screener 사이드바에 이메일 입력 → 유료판 해제 확인
5. (선택) 구독 revoke → Brevo 리스트에서 제거 확인

**Stripe (테스트 모드)**

1. Payment Link 테스트 결제 → Webhooks 로그 `200` 확인
2. Brevo 리스트 반영 → 사이드바 확인