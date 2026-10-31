# -*- coding: utf-8 -*-
"""개인정보 처리방침 초안.

변호사 검토 전 초안이다. 화면과 가입 동의 버전에 같은 POLICY_VERSION 을 쓴다.
연락처는 오너가 [담당자 이메일] 을 실제 주소로 바꾼 뒤 공개한다.
"""

POLICY_VERSION = "2026-10-31-draft"
CONTACT_PLACEHOLDER = "[담당자 이메일]"

# Brevo 컨택 속성. 스키마에 없으면 조용히 버려진다.
BREVO_CONSENT_ATTRIBUTES = {
    "CONSENT_AT": "text",
    "CONSENT_VERSION": "text",
}

_BODY = {
    "ko": """**[초안, 변호사 검토 전]**

# 개인정보 처리방침 (초안)

이 문서는 변호사 검토 전의 초안입니다. 공개 운영 전에 법률 검토를 받으세요.

## 1. 처리 목적
- 무료 뉴스레터 발송
- 분석 대상 종목 추가 요청의 접수와 처리 안내

## 2. 수집 항목
- 이메일
- 가입 경로 (utm_source, utm_medium, utm_campaign, utm_content, utm_term 와 이를 요약한 SOURCE)
- 종목 추가 요청을 한 경우, 요청한 티커
- 동의 시각과 동의 버전

## 3. 보유 기간
뉴스레터 수신 정보는 구독을 해지할 때까지 보관합니다. 해지 요청이 오면 발송 명단에서 지웁니다.

## 4. 처리 위탁과 국외 이전
이메일 발송과 연락처 보관은 Brevo(Sendinblue)에 맡깁니다. Brevo 서버는 대한민국 밖에 있을 수 있으며, 이 경우 개인정보가 국외로 이전됩니다.

## 5. 동의
가입 화면의 체크는 위 목적의 수집, 이용, 국외 이전에 대한 동의입니다. 동의하지 않으면 가입되지 않습니다.

## 6. 연락처
개인정보 관련 문의: {contact}

문서 버전: {version}
""",
    "en": """**[Draft, pending lawyer review]**

# Privacy notice (draft)

This text is a draft and has not been reviewed by a lawyer.

## 1. Purpose
- Sending the free newsletter
- Receiving requests to add a ticker and replying about that request

## 2. Data we collect
- Email address
- Signup source (utm_source, utm_medium, utm_campaign, utm_content, utm_term, and SOURCE derived from them)
- Requested ticker, if you ask for one
- Consent timestamp and consent version

## 3. Retention
Newsletter contact data is kept until you unsubscribe. After an unsubscribe request, the address is removed from the mailing list.

## 4. Processor and overseas transfer
Email delivery and contact storage are handled by Brevo (Sendinblue). Brevo servers may be outside Korea, so this is an overseas transfer of personal data.

## 5. Consent
The signup checkbox is consent to the collection, use, and overseas transfer described above. Signup does not proceed without it.

## 6. Contact
Privacy contact: {contact}

Document version: {version}
""",
    "ja": """**[草案, 弁護士レビュー前]**

# プライバシーポリシー (草案)

この文章は弁護士の確認前の草案です。

## 1. 利用目的
- 無料ニュースレターの送信
- 分析対象銘柄の追加依頼の受付と案内

## 2. 収集する項目
- メールアドレス
- 登録経路 (utm_source, utm_medium, utm_campaign, utm_content, utm_term と SOURCE)
- 銘柄追加を依頼した場合、そのティッカー
- 同意日時と同意バージョン

## 3. 保有期間
ニュースレターの連絡先は配信停止まで保管します。停止の依頼があれば配信リストから削除します。

## 4. 委託と国外移転
メール送信と連絡先の保管は Brevo (Sendinblue) に委託します。Brevo のサーバは韓国国外にある場合があり、その場合は個人情報の国外移転になります。

## 5. 同意
登録画面のチェックは、上記の収集、利用、国外移転への同意です。同意がない場合は登録しません。

## 6. 連絡先
個人情報に関する連絡先: {contact}

文書バージョン: {version}
""",
}


def markdown(lang: str = "ko") -> str:
    """처리방침 초안 마크다운. lang 이 없으면 한국어."""
    template = _BODY.get(lang) or _BODY["ko"]
    return template.format(contact=CONTACT_PLACEHOLDER, version=POLICY_VERSION)
