"""
KB Indonesia AI FDS - Admin Dashboard (Streamlit)
"""

import sys
sys.path.insert(0, ".")

import json
from datetime import datetime

import httpx
import plotly.express as px
import streamlit as st

API = "http://localhost:8000/api"

st.set_page_config(page_title="KB Indonesia AI FDS Admin", page_icon="🛡️", layout="wide")

# ===== Rule Descriptions (Korean) =====

RULE_INFO = {
    "mule_account_suspect": {
        "title": "대포통장 의심 거래",
        "icon": "🏦",
        "desc": "신규 개설 계좌에서 대규모 이체가 야간에 발생하는 패턴을 탐지합니다. 대포통장은 보이스피싱, 자금세탁 등 금융범죄의 핵심 수단이며, 범죄자가 단기간 내 계좌를 개설하고 즉시 대규모 이체를 실행하는 것이 전형적 수법입니다.",
        "trigger": "계좌 개설일 ≤ 신규 기준(30일) AND 대규모 금액 AND 야간(22~06시)",
        "example": "계좌를 개설한 지 5일 된 고객이 새벽 2시에 2억 루피아를 신규 수취인에게 이체",
    },
    "sim_swap_fraud": {
        "title": "SIM 스왑 사기",
        "icon": "📱",
        "desc": "최근 SIM 카드가 변경되고 신규 기기에서 즉시 이체가 실행되는 패턴을 탐지합니다. SIM 스왑 공격은 범죄자가 통신사를 속여 피해자의 전화번호를 탈취한 후 OTP 인증을 우회하여 계좌를 장악하는 수법입니다.",
        "trigger": "SIM 변경 AND 신규 기기 AND 대규모 금액",
        "example": "고객의 SIM이 2시간 전에 교체되고, 이전에 사용한 적 없는 기기에서 1억 루피아 이체를 시도",
    },
    "voice_phishing_suspect": {
        "title": "보이스피싱 의심 거래",
        "icon": "📞",
        "desc": "대규모 금액을 신규 수취인에게 보내면서 고객의 평소 거래 패턴과 크게 벗어나는 이상 거래를 탐지합니다. 보이스피싱 피해자는 범죄자의 지시에 따라 평소와 전혀 다른 금액을 처음 보는 계좌로 급히 송금하는 특성이 있습니다.",
        "trigger": "대규모 금액 AND 신규 수취인 AND 평균 대비 금액 이상치",
        "example": "월 평균 거래 금액이 300만 루피아인 고객이 갑자기 5천만 루피아를 처음 보는 수취인에게 이체",
    },
    "money_laundering_structuring": {
        "title": "자금세탁 분할거래 (Structuring)",
        "icon": "💰",
        "desc": "보고 기준 금액을 회피하기 위해 의도적으로 거래를 분할하는 패턴을 탐지합니다. 자금세탁범은 PPATK 보고 의무 금액 이하로 여러 건을 나누어 송금하여 감시망을 피하려 합니다.",
        "trigger": "일일 거래 건수 ≥ 분할 기준(5건) AND 건당 평균금액이 평소 평균의 30% 미만 AND 신규 수취인",
        "example": "5억 루피아 보고 기준을 피해 하루에 4천9백만씩 6건으로 나누어 이체",
    },
    "ppatk_ctr_threshold": {
        "title": "PPATK 의심거래보고(CTR) 기준 초과",
        "icon": "📋",
        "desc": "단일 거래 금액이 PPATK가 정한 의무 보고 기준(5억 루피아)을 초과하는 거래를 탐지합니다. 인도네시아 자금세탁방지법에 따라 일정 금액 이상의 거래는 의무적으로 보고해야 하며, 이를 자동으로 플래깅하여 규정 준수를 보장합니다.",
        "trigger": "거래 금액 ≥ PPATK CTR 기준 (기본 Rp 500,000,000)",
        "example": "고객이 7억 루피아를 단일 건으로 이체하여 법정 보고 기준 5억을 초과",
    },
    "high_risk_remittance": {
        "title": "고위험국 해외송금",
        "icon": "🌍",
        "desc": "FATF 지정 고위험국(북한, 이란, 미얀마 등)으로의 국제 송금을 탐지합니다. 고위험국 송금은 테러자금조달, 대량살상무기 확산금융, 제재 위반 위험이 높아 강화된 고객확인(EDD)이 필요합니다.",
        "trigger": "국제 송금 AND 수취국이 FATF 고위험국 목록 AND 대규모 금액",
        "example": "고객이 미얀마(MM) 소재 수취인에게 3억 루피아를 해외송금",
    },
    "blacklisted_recipient": {
        "title": "블랙리스트 수취인 거래",
        "icon": "🚫",
        "desc": "수취인이 내부 블랙리스트에 등록된 계좌인 경우를 탐지합니다. 과거 사기, 자금세탁 등 금융범죄에 연루되었거나 제재 대상으로 지정된 수취인과의 거래는 즉시 차단해야 합니다. 이 규칙은 LLM 판단과 무관하게 강제 차단(FORCE BLOCK)됩니다.",
        "trigger": "수취인 유형 = blacklisted",
        "example": "이전에 보이스피싱 대포통장으로 확인되어 블랙리스트에 등록된 계좌로 이체 시도",
    },
    "night_large_transfer": {
        "title": "야간 대규모 이체",
        "icon": "🌙",
        "desc": "야간 시간대(22:00~06:00)에 대규모 금액이 이체되는 거래를 탐지합니다. 정상 고객의 대부분 거래는 영업시간 내에 이루어지며, 야간 대규모 이체는 계좌 탈취나 무단 접근의 징후일 수 있습니다.",
        "trigger": "야간(22시~06시) AND 대규모 금액",
        "example": "새벽 3시에 8천만 루피아가 이체",
    },
    "abnormal_frequency": {
        "title": "비정상 거래 빈도",
        "icon": "⚡",
        "desc": "하루 거래 건수가 설정된 한도를 초과하는 비정상적 빈도의 거래를 탐지합니다. 계좌가 탈취되었거나 자동화된 범죄 도구로 악용되는 경우 단시간 내 다수 거래가 발생하는 패턴을 보입니다.",
        "trigger": "당일 거래 건수 > 빈도 임계값 (기본 10건)",
        "example": "평소 월 5건 거래하던 고객 계좌에서 하루에 15건의 이체가 발생",
    },
    "amount_anomaly": {
        "title": "거래 금액 이상치",
        "icon": "📊",
        "desc": "거래 금액이 고객의 평균 거래 금액 대비 설정된 배율(기본 3배)을 초과하는 이상 거래를 탐지합니다. 급격한 금액 증가는 보이스피싱 피해, 계좌 도용, 내부자 부정 등의 초기 징후일 수 있습니다.",
        "trigger": "거래 금액 ≥ 평균 거래 금액 × 이상치 배율 (기본 3.0배)",
        "example": "평균 거래 금액이 200만 루피아인 고객이 갑자기 1,500만 루피아(7.5배)를 이체",
    },
    "new_device_large_transfer": {
        "title": "신규 기기 대규모 이체",
        "icon": "💻",
        "desc": "이전에 사용한 적 없는 새로운 기기에서 대규모 금액이 이체되는 거래를 탐지합니다. 기기 변경과 동시에 대규모 이체가 발생하면 계정 탈취(Account Takeover)의 가능성이 높습니다.",
        "trigger": "신규 기기 AND 대규모 금액",
        "example": "등록된 적 없는 새 스마트폰에서 처음 로그인하여 즉시 1억 루피아를 이체",
    },
    "repeated_alerts": {
        "title": "반복 알림 발생 계좌",
        "icon": "🔔",
        "desc": "최근 30일 이내에 설정된 횟수(기본 2회) 이상의 FDS 알림이 발생한 계좌의 거래를 탐지합니다. 반복적으로 의심 거래가 발생하는 계좌는 조직적 범죄에 지속적으로 악용되고 있을 가능성이 높습니다.",
        "trigger": "최근 30일 알림 건수 ≥ 반복 알림 임계값 (기본 2건)",
        "example": "지난 30일간 이미 3번 의심 거래 알림이 발생한 계좌에서 다시 이체를 시도",
    },
    "dormant_account_reactivation": {
        "title": "휴면 계좌 재활성화 대규모 이체",
        "icon": "💤",
        "desc": "장기간(기본 180일) 휴면 상태였던 계좌가 갑자기 활성화되어 대규모 이체를 실행하는 패턴을 탐지합니다. 범죄자가 오래 방치된 계좌를 탈취하거나, 미리 개설해둔 대포통장을 일정 기간 후 활성화하는 수법에 해당합니다.",
        "trigger": "계좌 비활성 기간 > 휴면 기준(180일) AND 대규모 금액",
        "example": "2년간 거래가 전혀 없던 계좌에서 갑자기 3억 루피아가 이체",
    },
}

CONDITION_INFO = {
    "new_account_days": {"title": "신규 계좌 기준 (일)", "icon": "📅", "unit": "일"},
    "dormant_days": {"title": "휴면 계좌 기준 (일)", "icon": "💤", "unit": "일"},
    "high_frequency_threshold": {"title": "일일 거래 빈도 한도", "icon": "⚡", "unit": "건/일"},
    "large_amount_threshold": {"title": "대규모 거래 기준 금액", "icon": "💰", "unit": "IDR"},
    "very_large_amount_threshold": {"title": "PPATK CTR 보고 기준 금액", "icon": "📋", "unit": "IDR"},
    "amount_anomaly_multiplier": {"title": "금액 이상치 배율", "icon": "📊", "unit": "배"},
    "split_txn_min_count": {"title": "분할거래 최소 건수", "icon": "✂️", "unit": "건"},
    "recent_alerts_threshold": {"title": "반복 알림 기준 건수", "icon": "🔔", "unit": "건/30일"},
}


# ===== API Helpers =====

def api_get(path, **params):
    try:
        r = httpx.get(f"{API}{path}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        st.error("⚠️ API 서버에 연결할 수 없습니다. `python main.py`로 서버를 시작하세요.")
        return None
    except Exception as e:
        st.error(f"API 오류: {e}")
        return None


def api_put(path, body):
    try:
        r = httpx.put(f"{API}{path}", json=body, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API 오류: {e}")
        return None


def api_post(path, body):
    try:
        r = httpx.post(f"{API}{path}", json=body, timeout=60)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API 오류: {e}")
        return None


def api_delete(path):
    try:
        r = httpx.delete(f"{API}{path}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API 오류: {e}")
        return None


def _risk_icon(level):
    return {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(level, "⚪")


def _format_idr(amount):
    try:
        return f"Rp {float(amount):,.0f}"
    except (ValueError, TypeError):
        return str(amount)


# ===== Navigation =====

PAGES = [
    "📊 Dashboard",
    "📋 Transaction History",
    "🧪 Transaction Test",
    "⚙️ Rule Management",
    "🎚️ Condition Parameters",
    "📑 Policy Management",
    "🌍 High-Risk Countries",
    "🔧 Global Settings",
    "📝 Audit Log",
]

st.sidebar.title("🛡️ KB Indonesia FDS")
st.sidebar.caption("이상거래탐지시스템 관리 콘솔")
page = st.sidebar.radio("Navigation", PAGES, label_visibility="collapsed")


# ================================================================
# PAGE: Dashboard
# ================================================================
if page == "📊 Dashboard":
    st.title("📊 FDS 대시보드")
    st.caption("KB Indonesia 이상거래탐지시스템 현황")

    stats = api_get("/dashboard/stats")
    if not stats:
        st.stop()

    # KPI 카드
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("전체 건수", f"{stats['total_transactions']:,}")
    c2.metric("🔴 고위험", stats["high_risk_count"],
              help="룰엔진+LLM 판정 결과 HIGH인 건수")
    c3.metric("🟡 중위험", stats["medium_risk_count"])
    c4.metric("🟢 저위험", stats["low_risk_count"])
    c5.metric("🚫 차단", stats["blocked_count"],
              help="BLOCK 조치된 건수")
    c6.metric("⏱ 평균 처리", f"{stats['avg_processing_time_ms']:.0f}ms")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("위험도 분포")
        labels = ["HIGH", "MEDIUM", "LOW"]
        values = [stats["high_risk_count"], stats["medium_risk_count"], stats["low_risk_count"]]
        if any(values):
            fig = px.pie(values=values, names=labels, color=labels,
                         color_discrete_map={"HIGH": "#e74c3c", "MEDIUM": "#f39c12", "LOW": "#27ae60"})
            fig.update_layout(margin=dict(t=10, b=10), height=300)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("아직 평가된 거래가 없습니다.")

    with col2:
        st.subheader("사기 유형별 분포")
        dist = stats.get("fraud_type_distribution", {})
        if dist:
            fig = px.bar(x=list(dist.keys()), y=list(dist.values()),
                         labels={"x": "사기 유형", "y": "건수"})
            fig.update_layout(margin=dict(t=10, b=10), height=300, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("LLM이 판정한 사기 유형 데이터가 아직 없습니다.")

    # 조치 분포
    st.subheader("조치 현황")
    ac1, ac2, ac3 = st.columns(3)
    ac1.metric("🚫 BLOCK", stats["blocked_count"])
    ac2.metric("🔍 REVIEW", stats["review_count"])
    allow_count = stats["total_transactions"] - stats["blocked_count"] - stats["review_count"]
    ac3.metric("✅ ALLOW/ALERT", max(allow_count, 0))


# ================================================================
# PAGE: Transaction History
# ================================================================
elif page == "📋 Transaction History":
    st.title("📋 거래 평가 이력")
    st.caption("FDS가 평가한 거래 내역을 조회합니다.")

    # 필터
    fc1, fc2 = st.columns([1, 4])
    with fc1:
        risk_filter = st.selectbox("위험도 필터", ["전체", "HIGH", "MEDIUM", "LOW"])

    params = {"limit": 50}
    if risk_filter != "전체":
        params["risk_level"] = risk_filter

    history = api_get("/transactions", **params)
    if not history:
        st.info("평가된 거래가 없습니다. '🧪 Transaction Test'에서 테스트해보세요.")
        st.stop()

    for item in history:
        risk = item.get("final_risk_level", "LOW")
        icon = _risk_icon(risk)
        action = item.get("final_action", "")
        txn_id = item["transaction_id"]
        time_str = item.get("created_at", "")[:19]

        # raw_result에서 거래 상세 추출
        raw = {}
        try:
            raw = json.loads(item.get("raw_result", "{}"))
        except (json.JSONDecodeError, TypeError):
            pass

        # 거래 기본 정보 추출
        txn_data = raw.get("rule_engine_result", {})
        amount_str = ""
        txn_type_str = ""

        # raw_result 내 원본 데이터가 있으면 표시
        if raw:
            # FDSResult 구조에서는 직접 거래 데이터가 없으므로 rule 정보로 보완
            pass

        header_text = (
            f"{icon} **{txn_id}** | {risk} | {action} | "
            f"룰점수: {item['rule_risk_score']}/100 | {item['processing_time_ms']:.0f}ms | "
            f"{time_str}"
        )

        with st.expander(header_text):
            tab_rule, tab_llm = st.tabs(["🔧 룰엔진 결과", "🤖 LLM 평가"])

            with tab_rule:
                st.markdown(f"**룰엔진 위험 점수: {item['rule_risk_score']}/100**")
                rules = json.loads(item.get("triggered_rules", "[]"))
                if rules:
                    for r in rules:
                        rname = r["rule_name"]
                        info = RULE_INFO.get(rname, {})
                        rule_icon = info.get("icon", "📌")
                        rule_title = info.get("title", rname)
                        st.markdown(
                            f"- {rule_icon} **{rule_title}** (`{rname}`) — +{r['score']}점"
                        )
                        if info.get("desc"):
                            st.caption(f"   {info['desc'][:80]}...")
                else:
                    st.success("트리거된 규칙이 없습니다. 정상 거래로 판단되었습니다.")

            with tab_llm:
                if item.get("llm_reasoning"):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.metric("LLM 위험도", f"{item.get('llm_risk_level', 'N/A')}")
                        st.metric("LLM 점수", f"{item.get('llm_risk_score', 0)}/100")
                    with col_b:
                        st.metric("사기 유형", item.get("llm_fraud_type", "N/A"))
                        st.metric("신뢰도", f"{item.get('llm_confidence', 0)}%")
                    st.markdown("**LLM 판단 근거:**")
                    st.info(item.get("llm_reasoning", ""))
                else:
                    st.info("💡 LLM 평가가 호출되지 않았습니다 (룰엔진 점수가 임계값 미만).")


# ================================================================
# PAGE: Transaction Test
# ================================================================
elif page == "🧪 Transaction Test":
    st.title("🧪 거래 평가 테스트")

    tab_single, tab_batch = st.tabs(["📝 단건 테스트", "📦 배치 테스트"])

    with tab_single:
        st.caption("거래 정보를 입력하여 FDS 평가 결과를 확인합니다.")

        with st.form("test_form"):
            st.markdown("##### 거래 정보")
            c1, c2, c3 = st.columns(3)
            with c1:
                txn_type = st.selectbox("거래 유형", ["domestic_transfer", "interbank_transfer", "international_remittance"],
                                        format_func=lambda x: {"domestic_transfer": "국내이체", "interbank_transfer": "타행이체", "international_remittance": "해외송금"}.get(x, x))
                amount = st.number_input("금액 (IDR)", min_value=1, value=50_000_000, step=1_000_000,
                                         help="인도네시아 루피아 기준")
                account_age = st.number_input("계좌 개설일수", min_value=1, value=365,
                                              help="계좌 개설 후 경과 일수")
                recipient_type = st.selectbox("수취인 유형", ["existing", "new", "blacklisted"],
                                              format_func=lambda x: {"existing": "기존 수취인", "new": "신규 수취인", "blacklisted": "블랙리스트"}.get(x, x))

            with c2:
                recipient_country = st.text_input("수취국 코드", value="ID", help="2자리 국가코드 (예: ID, KP, IR)")
                is_night = st.checkbox("야간 거래 (22~06시)")
                is_new_dev = st.checkbox("신규 기기")
                sim_changed = st.checkbox("SIM 최근 변경")

            with c3:
                st.markdown("##### 고객 프로필")
                daily_count = st.number_input("당일 거래 건수", min_value=1, value=3)
                daily_amount = st.number_input("당일 총 이체액 (IDR)", min_value=0, value=100_000_000, step=1_000_000)
                avg_monthly = st.number_input("월 평균 거래 건수", min_value=1, value=10)
                avg_amount = st.number_input("평균 거래 금액 (IDR)", min_value=1, value=5_000_000, step=100_000)

            submitted = st.form_submit_button("🔍 FDS 평가 실행", type="primary", use_container_width=True)

        if submitted:
            payload = {"transaction": {
                "transaction_type": txn_type, "amount": amount, "currency": "IDR",
                "timestamp": datetime.now().isoformat(),
                "sender_account_id": "TEST-SENDER", "sender_account_age_days": account_age,
                "recipient_account_id": "TEST-RECIP", "recipient_type": recipient_type,
                "recipient_country": recipient_country,
                "is_night_transaction": is_night, "is_new_device": is_new_dev,
                "sim_changed_recently": sim_changed,
                "daily_txn_count_today": daily_count, "daily_amount_today": daily_amount,
                "avg_monthly_txn_count": avg_monthly, "avg_transaction_amount": avg_amount,
            }}

            with st.spinner("FDS 평가 중..."):
                data = api_post("/transactions/evaluate", payload)

            if data and data.get("result"):
                r = data["result"]
                risk = r["final_risk_level"]
                color = _risk_icon(risk)

                st.divider()
                rc1, rc2, rc3, rc4 = st.columns(4)
                rc1.metric("위험도", f"{color} {risk}")
                rc2.metric("조치", r["final_action"])
                rc3.metric("룰엔진 점수", f"{r['rule_engine_result']['risk_score']}/100")
                rc4.metric("처리 시간", f"{r['processing_time_ms']:.0f}ms")

                tab_r, tab_l = st.tabs(["🔧 룰엔진 상세", "🤖 LLM 상세"])

                with tab_r:
                    re = r["rule_engine_result"]
                    st.write(f"**정책:** {re['policy_name']} | **LLM 호출:** {'예' if re.get('should_invoke_llm') else '아니오'}")
                    for tr in re.get("triggered_rules", []):
                        info = RULE_INFO.get(tr["rule_name"], {})
                        st.write(f"- {info.get('icon', '📌')} **{info.get('title', tr['rule_name'])}** — +{tr['score']}점")

                with tab_l:
                    if r.get("llm_evaluation"):
                        llm = r["llm_evaluation"]
                        st.write(f"**LLM 점수:** {llm['risk_score']}/100 | **신뢰도:** {llm['confidence']}%")
                        st.write(f"**사기 유형:** {llm.get('fraud_type', 'N/A')}")
                        st.info(f"**판단 근거:** {llm.get('reasoning', '')}")
                    else:
                        st.info("LLM이 호출되지 않았습니다.")

    with tab_batch:
        st.caption("랜덤 거래를 생성하여 배치로 FDS 평가를 실행합니다.")
        count = st.slider("생성할 거래 건수", 5, 50, 20)
        if st.button("🚀 배치 생성 및 평가", type="primary"):
            with st.spinner(f"{count}건 거래 생성 및 평가 중..."):
                from data.sample_transactions import generate_transactions
                txns = generate_transactions(count)
                payloads = [t.model_dump(mode="json") for t in txns]
                results = api_post("/transactions/batch", payloads)

            if results:
                high = sum(1 for r in results if r["result"]["final_risk_level"] == "HIGH")
                med = sum(1 for r in results if r["result"]["final_risk_level"] == "MEDIUM")
                low = sum(1 for r in results if r["result"]["final_risk_level"] == "LOW")
                st.success(f"✅ {len(results)}건 평가 완료: 🔴 {high} HIGH | 🟡 {med} MEDIUM | 🟢 {low} LOW")
                st.rerun()


# ================================================================
# PAGE: Rule Management
# ================================================================
elif page == "⚙️ Rule Management":
    st.title("⚙️ 탐지 규칙 관리")
    st.caption("FDS 탐지 규칙의 점수와 활성화 상태를 관리합니다. 변경 즉시 적용되며 감사 로그에 기록됩니다.")

    rules = api_get("/rules")
    if not rules:
        st.stop()

    # 강제 차단 규칙 표시
    st.info("🔒 **강제 차단 규칙**: `blacklisted_recipient`, `high_risk_remittance`는 LLM 판단과 무관하게 항상 BLOCK 처리됩니다.")
    st.divider()

    for rule in rules:
        name = rule["rule_name"]
        info = RULE_INFO.get(name, {"title": name, "icon": "📌", "desc": "", "trigger": "", "example": ""})
        is_force_block = name in ("blacklisted_recipient", "high_risk_remittance")

        with st.container(border=True):
            # 헤더: 아이콘 + 한국어 제목 + 활성화 상태
            hc1, hc2, hc3 = st.columns([5, 2, 1])

            with hc1:
                badge = " 🔒" if is_force_block else ""
                enabled_mark = "✅" if rule["enabled"] else "❌"
                st.markdown(f"### {info['icon']} {info['title']}{badge}")
                st.caption(f"`{name}` | 현재 점수: **{rule['score']}점** | {enabled_mark}")

            with hc2:
                new_score = st.number_input(
                    "점수", min_value=0, max_value=100,
                    value=rule["score"], key=f"score_{name}",
                    help="이 규칙이 트리거될 때 부여할 위험 점수 (0~100)",
                )

            with hc3:
                new_enabled = st.toggle("활성", value=bool(rule["enabled"]), key=f"en_{name}")

            # 상세 설명
            with st.expander("📖 규칙 상세 설명", expanded=False):
                st.markdown(f"**설명:** {info['desc']}")
                st.markdown(f"**발동 조건:** `{info['trigger']}`")
                st.markdown(f"**예시:** {info['example']}")

            # 저장 버튼
            if new_score != rule["score"] or new_enabled != bool(rule["enabled"]):
                if st.button(f"💾 변경 저장", key=f"save_{name}", type="primary"):
                    api_put(f"/rules/{name}", {"score": new_score, "enabled": new_enabled})
                    st.success(f"✅ {info['title']} 업데이트 완료")
                    st.rerun()


# ================================================================
# PAGE: Condition Parameters
# ================================================================
elif page == "🎚️ Condition Parameters":
    st.title("🎚️ 탐지 조건 임계값 설정")
    st.caption("규칙을 구성하는 개별 조건 함수의 임계값을 조정합니다. 변경 즉시 적용됩니다.")

    params = api_get("/conditions")
    if not params:
        st.stop()

    SLIDER_CONFIG = {
        "new_account_days": (1, 365, 1),
        "dormant_days": (30, 730, 10),
        "high_frequency_threshold": (3, 50, 1),
        "large_amount_threshold": (1_000_000, 500_000_000, 1_000_000),
        "very_large_amount_threshold": (100_000_000, 2_000_000_000, 10_000_000),
        "amount_anomaly_multiplier": (1.0, 20.0, 0.5),
        "split_txn_min_count": (2, 30, 1),
        "recent_alerts_threshold": (1, 10, 1),
    }

    for p in params:
        name = p["param_name"]
        ptype = p["param_type"]
        current = float(p["param_value"]) if ptype == "float" else int(p["param_value"])
        info = CONDITION_INFO.get(name, {"title": name, "icon": "⚙️", "unit": ""})

        with st.container(border=True):
            cc1, cc2 = st.columns([2, 3])

            with cc1:
                st.markdown(f"### {info['icon']} {info['title']}")
                st.caption(f"`{name}` | {p['description']}")
                if info["unit"] == "IDR":
                    st.write(f"현재 값: **{_format_idr(current)}**")
                elif info["unit"] == "배":
                    st.write(f"현재 값: **{current:.1f}배**")
                else:
                    st.write(f"현재 값: **{int(current):,} {info['unit']}**")

            with cc2:
                cfg = SLIDER_CONFIG.get(name, (0, 1000, 1))
                mn, mx, step = cfg

                if ptype == "float":
                    new_val = st.slider(
                        f"{info['title']}", min_value=float(mn), max_value=float(mx),
                        value=float(current), step=float(step), key=f"cond_{name}",
                        label_visibility="collapsed",
                    )
                    changed = abs(new_val - current) > 0.01
                    val_str = str(new_val)
                else:
                    new_val = st.slider(
                        f"{info['title']}", min_value=int(mn), max_value=int(mx),
                        value=int(current), step=int(step), key=f"cond_{name}",
                        label_visibility="collapsed",
                    )
                    changed = new_val != current
                    val_str = str(new_val)

                if changed:
                    if info["unit"] == "IDR":
                        display = _format_idr(new_val)
                    elif info["unit"] == "배":
                        display = f"{new_val:.1f}배"
                    else:
                        display = f"{int(new_val):,} {info['unit']}"
                    if st.button(f"💾 {display} 으로 변경", key=f"save_cond_{name}", type="primary"):
                        api_put(f"/conditions/{name}", {"param_value": val_str})
                        st.success(f"✅ {info['title']} → {display}")
                        st.rerun()


# ================================================================
# PAGE: Policy Management
# ================================================================
elif page == "📑 Policy Management":
    st.title("📑 정책 관리")
    st.caption("정책별로 적용할 규칙을 관리합니다. 정책은 거래 유형에 따라 자동 선택됩니다.")

    policies = api_get("/policies")
    if not policies:
        st.stop()

    POLICY_NAMES = {
        "domestic_transfer": "🏠 국내이체 정책",
        "international_remittance": "✈️ 해외송금 정책",
    }

    for policy_name, rules in policies.items():
        display_name = POLICY_NAMES.get(policy_name, policy_name)
        st.subheader(f"{display_name}")
        st.caption(f"`{policy_name}` — {len(rules)}개 규칙 할당")

        for rule in rules:
            rname = rule["rule_name"]
            info = RULE_INFO.get(rname, {"title": rname, "icon": "📌"})
            enabled_in_policy = bool(rule["enabled"])
            rule_enabled = bool(rule.get("rule_enabled", 1))

            with st.container(border=True):
                pc1, pc2, pc3 = st.columns([5, 1, 1])

                with pc1:
                    if not rule_enabled:
                        status = "❌ 규칙 비활성"
                    elif not enabled_in_policy:
                        status = "⏸️ 정책에서 제외"
                    else:
                        status = "✅ 활성"
                    st.write(f"{info['icon']} **{info['title']}** — 점수: {rule.get('score', '?')}점 — {status}")

                with pc2:
                    new_en = st.toggle("포함", value=enabled_in_policy, key=f"pol_{policy_name}_{rname}")

                with pc3:
                    if new_en != enabled_in_policy:
                        if st.button("💾", key=f"save_pol_{policy_name}_{rname}"):
                            api_put(f"/policies/{policy_name}/rules/{rname}", {"enabled": new_en})
                            st.success(f"{'활성화' if new_en else '비활성화'}: {info['title']}")
                            st.rerun()

        st.divider()


# ================================================================
# PAGE: High-Risk Countries
# ================================================================
elif page == "🌍 High-Risk Countries":
    st.title("🌍 FATF 고위험국 관리")
    st.caption("FATF 지정 고위험국 목록을 관리합니다. 해외송금 규칙(`high_risk_remittance`)에서 사용됩니다.")

    countries = api_get("/countries")
    if countries is None:
        st.stop()

    if countries:
        for c in countries:
            code = c["country_code"]
            cc1, cc2 = st.columns([5, 1])
            cc1.write(f"🏳️ **{code}** — {c['country_name']}")
            if cc2.button("🗑️ 삭제", key=f"del_{code}"):
                api_delete(f"/countries/{code}")
                st.success(f"✅ {code} 삭제 완료")
                st.rerun()
    else:
        st.warning("등록된 고위험국이 없습니다.")

    st.divider()
    st.subheader("➕ 고위험국 추가")
    with st.form("add_country"):
        ac1, ac2 = st.columns(2)
        new_code = ac1.text_input("국가 코드 (2자리)", max_chars=2, placeholder="XX")
        new_name = ac2.text_input("국가명", placeholder="Country Name")
        if st.form_submit_button("➕ 추가", type="primary"):
            if new_code and new_name:
                api_post("/countries", {"country_code": new_code.upper(), "country_name": new_name})
                st.success(f"✅ {new_code.upper()} 추가 완료")
                st.rerun()


# ================================================================
# PAGE: Global Settings
# ================================================================
elif page == "🔧 Global Settings":
    st.title("🔧 글로벌 설정")
    st.caption("FDS 시스템의 핵심 동작 파라미터를 설정합니다.")

    settings_data = api_get("/settings")
    if not settings_data:
        st.stop()

    SETTING_META = {
        "llm_threshold": {
            "title": "LLM 호출 임계값",
            "icon": "🤖",
            "min": 0, "max": 100, "step": 5,
            "help": "룰엔진 점수가 이 값 이상이면 LLM(GPT-4o)을 호출하여 2차 평가합니다. 낮출수록 LLM 호출 빈도 증가 (비용 상승), 높일수록 탐지 정밀도 감소.",
        },
        "block_threshold": {
            "title": "자동 차단 임계값",
            "icon": "🚫",
            "min": 0, "max": 100, "step": 5,
            "help": "LLM 미호출 시, 룰엔진 점수가 이 값 이상이면 자동으로 BLOCK 처리합니다.",
        },
        "rag_top_k": {
            "title": "RAG 유사 사례 검색 수",
            "icon": "🔍",
            "min": 1, "max": 10, "step": 1,
            "help": "LLM 평가 시 ChromaDB에서 검색할 유사 사기 사례 수. 많을수록 맥락이 풍부하지만 토큰 비용 증가.",
        },
    }

    for s in settings_data:
        key = s["key"]
        meta = SETTING_META.get(key, {"title": key, "icon": "⚙️", "min": 0, "max": 100, "step": 1, "help": ""})

        with st.container(border=True):
            sc1, sc2 = st.columns([2, 3])

            with sc1:
                st.markdown(f"### {meta['icon']} {meta['title']}")
                st.caption(s["description"])
                st.write(f"현재 값: **{s['value']}**")

            with sc2:
                current = int(s["value"])
                new_val = st.slider(
                    meta["title"],
                    min_value=meta["min"], max_value=meta["max"],
                    value=current, step=meta["step"],
                    key=f"setting_{key}",
                    help=meta["help"],
                    label_visibility="collapsed",
                )

                if new_val != current:
                    if st.button(f"💾 {new_val}으로 변경", key=f"save_setting_{key}", type="primary"):
                        api_put(f"/settings/{key}", {"value": str(new_val)})
                        st.success(f"✅ {meta['title']} → {new_val}")
                        st.rerun()


# ================================================================
# PAGE: Audit Log
# ================================================================
elif page == "📝 Audit Log":
    st.title("📝 설정 변경 감사 로그")
    st.caption("모든 FDS 설정 변경 이력을 추적합니다. OJK 감독 검사 대응용.")

    log = api_get("/audit-log", limit=200)
    if not log:
        st.info("감사 로그가 비어 있습니다.")
        st.stop()

    # 필터
    fc1, fc2 = st.columns([1, 4])
    with fc1:
        table_filter = st.selectbox("대상 필터", ["전체", "rule_configs", "condition_params", "policy_configs", "global_settings", "high_risk_countries"])

    filtered = log
    if table_filter != "전체":
        filtered = [e for e in log if e["table_name"] == table_filter]

    st.write(f"**{len(filtered)}건** 표시 중")

    ACTION_LABELS = {"update": "✏️ 변경", "add": "➕ 추가", "delete": "🗑️ 삭제"}
    TABLE_LABELS = {
        "rule_configs": "탐지 규칙",
        "condition_params": "조건 임계값",
        "policy_configs": "정책 할당",
        "global_settings": "글로벌 설정",
        "high_risk_countries": "고위험국",
    }

    for entry in filtered:
        action_label = ACTION_LABELS.get(entry["action"], entry["action"])
        table_label = TABLE_LABELS.get(entry["table_name"], entry["table_name"])
        time_str = entry.get("created_at", "")[:19]

        with st.container(border=True):
            ec1, ec2 = st.columns([1, 4])
            with ec1:
                st.markdown(f"**{action_label}**")
                st.caption(time_str)
            with ec2:
                st.write(f"**{table_label}** → `{entry['record_key']}`")
                if entry.get("old_value"):
                    st.caption(f"변경 전: {entry['old_value'][:200]}")
                if entry.get("new_value"):
                    st.caption(f"변경 후: {entry['new_value'][:200]}")
