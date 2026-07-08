# -*- coding: utf-8 -*-
"""관리자 페이지 — 배포된 대시보드 URL에 ?admin=1 을 붙이면 뜬다(로컬 스크립트 실행 불필요).

일반 방문자의 사이드바/네비게이션에는 전혀 노출되지 않는다 — URL을 알아도 config.admin_password()
비밀번호를 통과해야 실제 기능이 보인다. app.py 가 st.query_params 를 보고 이 render()를 호출한 뒤
st.stop() 한다(평소 대시보드는 렌더링하지 않음).

유료 구독자 추가/제거/조회는 paid_gate.list_paid_subscribers/add_paid_subscriber/
remove_paid_subscribers 를 그대로 쓴다 — 로컬 CLI(scripts/manage_paid_subscribers.py)와
동일한 함수라 두 경로가 어긋나지 않는다.
"""
import csv
import hmac
import io

import pandas as pd
import streamlit as st

import config
import paid_gate
import waitlist


def _extract_emails_from_csv(text: str) -> list:
    """업로드된 CSV 텍스트에서 이메일 형식인 셀만 모아 소문자·중복제거(순서유지)로 반환한다.
    헤더 유무·열 위치·구분자에 관계없이 '이메일처럼 생긴 셀'만 골라내므로 다양한 CSV를 관대하게 받는다."""
    seen, out = set(), []
    for row in csv.reader(io.StringIO(text)):
        for cell in row:
            email = cell.strip().lower()
            if email and email not in seen and waitlist.is_valid_email(email):
                seen.add(email)
                out.append(email)
    return out


def render() -> None:
    st.title("🔐 관리자 페이지")

    admin_pw = config.admin_password()
    if not admin_pw:
        st.error("ADMIN_PASSWORD가 설정되지 않았습니다 — secrets.json 또는 환경변수로 등록하세요.")
        return

    if not st.session_state.get("admin_authed"):
        pw = st.text_input("비밀번호", type="password", key="admin_pw_input")
        if st.button("로그인", key="admin_login_btn"):
            if pw and hmac.compare_digest(pw, admin_pw):
                st.session_state["admin_authed"] = True
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않습니다.")
        return

    top1, top2 = st.columns([5, 1])
    top1.success("인증됨")
    if top2.button("로그아웃", key="admin_logout_btn"):
        st.session_state.pop("admin_authed", None)
        st.rerun()

    st.divider()
    st.subheader("유료 구독자 관리")
    st.caption("결제 자동화(webhook)를 붙이기 전, 관리자가 직권으로 Brevo 유료 리스트를 관리합니다.")

    if not config.brevo_api_key() or not config.brevo_paid_list_id():
        st.warning("brevo_api_key / brevo_paid_list_id가 설정되지 않았습니다.")
        return

    subs = paid_gate.list_paid_subscribers()
    st.caption(f"현재 유료 구독자 **{len(subs)}명**")
    if subs:
        query = st.text_input(
            "이메일 검색", key="admin_search", placeholder="이메일 일부로 검색",
            label_visibility="collapsed",
        ).strip().lower()
        rows = []
        for s in sorted(subs, key=lambda s: s.get("email") or ""):
            email = s.get("email") or ""
            attrs = s.get("attributes") or {}
            expires = str(attrs.get("EXPIRES_AT") or "")[:10]
            if expires:
                status = "⛔ 만료됨" if paid_gate.is_expired(expires) else f"~{expires}"
            else:
                status = "영구"
            rows.append({
                "이메일": email,
                "출처": attrs.get("SOURCE", ""),
                "등록일": str(attrs.get("JOINED_AT", ""))[:10],
                "만료일": expires,
                "상태": status,
            })
        if query:
            rows = [r for r in rows if query in r["이메일"].lower()]
        st.caption(f"표시 {len(rows)}명" + (f" (검색: '{query}')" if query else ""))
        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True, width="stretch")
        st.download_button(
            "⬇️ 현재 명단 CSV 내려받기", data=df.to_csv(index=False).encode("utf-8-sig"),
            file_name="paid_subscribers.csv", mime="text/csv", key="admin_csv_download",
        )

    st.markdown("**추가**")
    # st.form 으로 감싸 위젯 값과 제출을 원자적으로 처리한다 — 폼 밖 버튼이라면 입력 직후 클릭 시
    # 값이 아직 커밋되기 전(blur 전)일 수 있으나, 폼은 제출 시점에 모든 값을 한꺼번에 읽는다.
    with st.form("admin_add_form", clear_on_submit=True):
        new_emails = st.text_area(
            "이메일(줄바꿈 또는 쉼표로 여러 개)", key="admin_add_emails", label_visibility="collapsed",
            placeholder="reader1@example.com\nreader2@example.com",
        )
        add_expiry = st.date_input(
            "만료일(선택 — 비우면 영구, 지정하면 그날까지만 접근)", value=None,
            key="admin_add_expiry", format="YYYY-MM-DD",
        )
        add_submitted = st.form_submit_button("➕ 추가")
    if add_submitted:
        emails = [e.strip() for e in new_emails.replace(",", "\n").splitlines() if e.strip()]
        if not emails:
            st.warning("이메일을 입력하세요.")
        else:
            exp = add_expiry.isoformat() if add_expiry else ""
            # st.rerun() 하면 결과 메시지가 즉시 사라지므로 세션에 담아 다음 렌더에서 한 번 띄운다.
            st.session_state["admin_op_result"] = [
                (email, paid_gate.add_paid_subscriber(email, exp)) for email in emails
            ]
            st.rerun()

    st.markdown("**CSV 일괄 업로드**")
    st.caption("이메일이 담긴 CSV를 올리면 형식이 맞는 셀만 골라 일괄 추가합니다(헤더·열 위치 무관).")
    with st.form("admin_csv_form", clear_on_submit=True):
        csv_file = st.file_uploader(
            "CSV 파일", type=["csv"], key="admin_csv_file", label_visibility="collapsed",
        )
        csv_expiry = st.date_input(
            "만료일(선택 — 이 배치 전체에 적용)", value=None, key="admin_csv_expiry", format="YYYY-MM-DD",
        )
        csv_submitted = st.form_submit_button("📤 업로드 추가")
    if csv_submitted:
        if csv_file is None:
            st.warning("CSV 파일을 선택하세요.")
        else:
            emails = _extract_emails_from_csv(csv_file.getvalue().decode("utf-8-sig", errors="replace"))
            if not emails:
                st.warning("CSV에서 유효한 이메일을 찾지 못했습니다.")
            else:
                exp = csv_expiry.isoformat() if csv_expiry else ""
                st.session_state["admin_op_result"] = [
                    (email, paid_gate.add_paid_subscriber(email, exp)) for email in emails
                ]
                st.rerun()

    for email, ok in st.session_state.pop("admin_op_result", []):
        (st.success if ok else st.error)(f"{'✅' if ok else '❌'} {email}")

    st.markdown("**제거**")
    existing_emails = [s.get("email") for s in subs]
    to_remove = st.multiselect(
        "제거할 이메일 선택", options=existing_emails, key="admin_remove_select",
        label_visibility="collapsed",
    )
    if st.button("🗑️ 제거", key="admin_remove_btn"):
        if not to_remove:
            st.warning("제거할 이메일을 선택하세요.")
        else:
            paid_gate.remove_paid_subscribers(to_remove)
            st.success(f"{len(to_remove)}명 제거됨")
            st.rerun()
