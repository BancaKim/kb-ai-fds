"""
Rules: 조건(Condition)을 조합하여 규칙을 구성한다.
규칙의 점수와 활성화 상태는 DB에서 동적으로 로드된다.
"""

from dataclasses import dataclass
from typing import Callable

from models.schemas import Transaction
from rule_engine.conditions import (
    has_recent_alerts,
    has_multiple_login_attempts,
    is_amount_anomaly,
    is_bi_fast_transfer,
    is_blacklisted_recipient,
    is_dormant_reactivated,
    is_full_balance_withdrawal,
    is_high_frequency,
    is_high_risk_country,
    is_international_transfer,
    is_ip_country_mismatch,
    is_large_amount,
    is_limit_recently_changed,
    is_new_account,
    is_new_device,
    is_new_recipient,
    is_night_transaction,
    is_sim_changed,
    is_split_transaction,
    is_very_large_amount,
)
from db.database import get_rule_configs


@dataclass
class Rule:
    name: str
    description: str
    score: int
    enabled: bool
    check: Callable[[Transaction], bool]


# 규칙 로직 (조건 조합) - 이것은 코드로 정의
RULE_CHECKS: dict[str, Callable[[Transaction], bool]] = {
    "mule_account_suspect": lambda txn: (
        is_new_account(txn) and is_large_amount(txn) and is_night_transaction(txn)
    ),
    "sim_swap_fraud": lambda txn: (
        is_sim_changed(txn) and is_new_device(txn) and is_large_amount(txn)
    ),
    "voice_phishing_suspect": lambda txn: (
        is_large_amount(txn) and is_new_recipient(txn) and is_amount_anomaly(txn)
    ),
    "money_laundering_structuring": lambda txn: (
        is_split_transaction(txn) and is_new_recipient(txn)
    ),
    "ppatk_ctr_threshold": lambda txn: is_very_large_amount(txn),
    "high_risk_remittance": lambda txn: (
        is_international_transfer(txn) and is_high_risk_country(txn) and is_large_amount(txn)
    ),
    "blacklisted_recipient": lambda txn: is_blacklisted_recipient(txn),
    "night_large_transfer": lambda txn: (
        is_night_transaction(txn) and is_large_amount(txn)
    ),
    "abnormal_frequency": lambda txn: is_high_frequency(txn),
    "amount_anomaly": lambda txn: is_amount_anomaly(txn),
    "new_device_large_transfer": lambda txn: (
        is_new_device(txn) and is_large_amount(txn)
    ),
    "repeated_alerts": lambda txn: has_recent_alerts(txn),
    "dormant_account_reactivation": lambda txn: (
        is_dormant_reactivated(txn) and is_large_amount(txn)
    ),
    # --- 신규 규칙 (ATO, 채널, IP) ---
    "account_takeover_suspect": lambda txn: (
        is_limit_recently_changed(txn) and is_new_device(txn) and is_large_amount(txn)
    ),
    "credential_stuffing_ato": lambda txn: (
        has_multiple_login_attempts(txn) and is_new_device(txn)
    ),
    "full_balance_withdrawal": lambda txn: (
        is_full_balance_withdrawal(txn) and (is_new_device(txn) or is_night_transaction(txn))
    ),
    "bi_fast_rapid_fan_out": lambda txn: (
        is_bi_fast_transfer(txn) and is_high_frequency(txn) and is_new_recipient(txn)
    ),
    "ip_mismatch_large_transfer": lambda txn: (
        is_ip_country_mismatch(txn) and is_large_amount(txn)
    ),
    "night_sim_device_combo": lambda txn: (
        is_night_transaction(txn) and is_sim_changed(txn) and is_new_device(txn)
    ),
}


def get_active_rules() -> list[Rule]:
    """DB에서 규칙 설정을 로드하고, 활성화된 규칙만 반환한다."""
    configs = get_rule_configs()
    rules = []
    for cfg in configs:
        check = RULE_CHECKS.get(cfg["rule_name"])
        if check is None:
            continue
        rules.append(Rule(
            name=cfg["rule_name"],
            description=cfg["description"],
            score=cfg["score"],
            enabled=bool(cfg["enabled"]),
            check=check,
        ))
    return rules
