"""
Policy Engine: DB에서 정책/규칙 설정을 동적으로 로드하여 평가한다.
카테고리별 최대값 합산으로 중복 점수 방지.
"""

from models.schemas import (
    Transaction,
    TransactionType,
    RuleEngineResult,
    TriggeredRule,
)
from db.database import get_policy_rule_names, get_setting
from rule_engine.rules import get_active_rules


# 규칙 카테고리 매핑 — 카테고리별 최대값 합산으로 중복 점수 방지
RULE_CATEGORIES = {
    "device_security": [
        "sim_swap_fraud", "new_device_large_transfer",
        "credential_stuffing_ato", "night_sim_device_combo",
    ],
    "amount_pattern": [
        "amount_anomaly", "night_large_transfer", "full_balance_withdrawal",
    ],
    "account_risk": [
        "mule_account_suspect", "dormant_account_reactivation",
        "account_takeover_suspect",
    ],
    "recipient_risk": [
        "blacklisted_recipient", "high_risk_remittance",
        "voice_phishing_suspect",
    ],
    "frequency_pattern": [
        "abnormal_frequency", "money_laundering_structuring",
        "bi_fast_rapid_fan_out",
    ],
    "regulatory": ["ppatk_ctr_threshold"],
    "behavioral": ["repeated_alerts", "ip_mismatch_large_transfer"],
}


def _calculate_risk_score(triggered: list[TriggeredRule]) -> int:
    """카테고리별 최대값 + 카테고리간 합산 (중복 점수 방지)"""
    rule_to_cat: dict[str, str] = {}
    for cat, rules in RULE_CATEGORIES.items():
        for r in rules:
            rule_to_cat[r] = cat

    cat_scores: dict[str, int] = {}
    for rule in triggered:
        cat = rule_to_cat.get(rule.rule_name, "uncategorized")
        cat_scores[cat] = max(cat_scores.get(cat, 0), rule.score)

    return min(sum(cat_scores.values()), 100)


def _get_policy_name(txn: Transaction) -> str:
    """채널 인식 정책 결정"""
    if txn.transaction_type == TransactionType.INTERNATIONAL_REMITTANCE:
        return "international_remittance"
    # 채널별 정책 분기 (향후 확장)
    channel = getattr(txn, 'channel', None)
    if channel and str(channel) == 'qris':
        return "qris_payment"
    return "domestic_transfer"


def evaluate(txn: Transaction) -> RuleEngineResult:
    """거래를 룰엔진으로 평가한다. 규칙/정책은 DB에서 동적 로드."""
    policy_name = _get_policy_name(txn)

    # DB에서 정책에 속한 활성 규칙 이름 목록 (폴백 포함)
    policy_rule_names = get_policy_rule_names(policy_name)
    if not policy_rule_names and policy_name != "domestic_transfer":
        policy_name = "domestic_transfer"
        policy_rule_names = get_policy_rule_names(policy_name)
    policy_rule_set = set(policy_rule_names)

    # DB에서 모든 규칙 설정 로드
    all_rules = get_active_rules()

    triggered: list[TriggeredRule] = []

    for rule in all_rules:
        if not rule.enabled:
            continue
        if rule.name not in policy_rule_set:
            continue
        if rule.check(txn):
            triggered.append(
                TriggeredRule(
                    rule_name=rule.name,
                    description=rule.description,
                    score=rule.score,
                )
            )

    # 카테고리별 최대값 합산 방식으로 위험 점수 산출
    risk_score = _calculate_risk_score(triggered)

    # 동적 임계값
    llm_threshold = int(get_setting("llm_threshold", "50"))
    should_invoke_llm = risk_score >= llm_threshold

    return RuleEngineResult(
        risk_score=risk_score,
        triggered_rules=triggered,
        should_invoke_llm=should_invoke_llm,
        policy_name=policy_name,
    )
