"""
Conditions: 룰엔진의 기본 빌딩 블록 (당근페이 레고 블록 방식)
파라미터는 DB에서 동적으로 로드된다.
"""

from db.database import get_condition_value, get_high_risk_country_codes
from models.schemas import Transaction, RecipientType


# --- 계좌 속성 조건 ---

def is_new_account(txn: Transaction, days: int = None) -> bool:
    if days is None:
        days = get_condition_value("new_account_days", 30)
    return txn.sender_account_age_days <= days


def is_dormant_reactivated(txn: Transaction, days: int = None) -> bool:
    if days is None:
        days = get_condition_value("dormant_days", 180)
    return txn.sender_account_age_days > days and txn.daily_txn_count_today <= 2


# --- 거래 패턴 조건 ---

def is_high_frequency(txn: Transaction, threshold: int = None) -> bool:
    if threshold is None:
        threshold = get_condition_value("high_frequency_threshold", 20)
    return txn.daily_txn_count_today > threshold


def is_large_amount(txn: Transaction, threshold: float = None) -> bool:
    if threshold is None:
        threshold = get_condition_value("large_amount_threshold", 50_000_000)
    return txn.amount >= threshold


def is_very_large_amount(txn: Transaction, threshold: float = None) -> bool:
    if threshold is None:
        threshold = get_condition_value("very_large_amount_threshold", 500_000_000)
    return txn.amount >= threshold


def is_night_transaction(txn: Transaction) -> bool:
    if txn.is_night_transaction:
        return True
    hour = txn.timestamp.hour
    return hour >= 22 or hour < 6


def is_amount_anomaly(txn: Transaction, multiplier: float = None) -> bool:
    if multiplier is None:
        multiplier = get_condition_value("amount_anomaly_multiplier", 5.0)
    if txn.avg_transaction_amount <= 0:
        return False
    return txn.amount >= txn.avg_transaction_amount * multiplier


def is_split_transaction(txn: Transaction, min_count: int = None) -> bool:
    if min_count is None:
        min_count = get_condition_value("split_txn_min_count", 5)
    avg_per_txn = txn.daily_amount_today / max(txn.daily_txn_count_today, 1)
    return (
        txn.daily_txn_count_today >= min_count
        and avg_per_txn < txn.avg_transaction_amount * 0.3
    )


# --- 수취인 속성 조건 ---

def is_new_recipient(txn: Transaction) -> bool:
    return txn.recipient_type == RecipientType.NEW


def is_blacklisted_recipient(txn: Transaction) -> bool:
    return txn.recipient_type == RecipientType.BLACKLISTED


def is_high_risk_country(txn: Transaction) -> bool:
    codes = get_high_risk_country_codes()
    return txn.recipient_country.upper() in codes


def is_international_transfer(txn: Transaction) -> bool:
    return txn.recipient_country.upper() != "ID"


# --- 디바이스/보안 조건 ---

def is_new_device(txn: Transaction) -> bool:
    return txn.is_new_device


def is_sim_changed(txn: Transaction) -> bool:
    return txn.sim_changed_recently


# --- 복합 조건 ---

def has_recent_alerts(txn: Transaction, threshold: int = None) -> bool:
    if threshold is None:
        threshold = get_condition_value("recent_alerts_threshold", 2)
    return txn.recent_alerts_30d >= threshold


# --- 잔액/인증 조건 (신규) ---

def is_full_balance_withdrawal(txn: Transaction) -> bool:
    """전액 인출 탐지 — ATO/사기의 핵심 지표"""
    balance = getattr(txn, 'account_balance_before', 0)
    if balance <= 0:
        return False
    return txn.amount >= balance * 0.9


def is_limit_recently_changed(txn: Transaction) -> bool:
    """한도 변경 직후 대량이체 — ATO 의심"""
    return getattr(txn, 'limit_recently_changed', False)


def has_multiple_login_attempts(txn: Transaction, threshold: int = None) -> bool:
    """다수 로그인 시도 — credential stuffing/ATO"""
    if threshold is None:
        threshold = get_condition_value("login_attempt_threshold", 5)
    return getattr(txn, 'login_attempts_today', 0) >= threshold


# --- IP/채널 조건 (신규) ---

def is_ip_country_mismatch(txn: Transaction) -> bool:
    """IP 국가와 계정 국가(ID) 불일치"""
    ip_country = getattr(txn, 'ip_country', 'ID')
    return ip_country.upper() != 'ID'


def is_bi_fast_transfer(txn: Transaction) -> bool:
    """BI-FAST 채널 여부 (실시간 소액이체 — 사기에 선호)"""
    channel = str(getattr(txn, 'channel', ''))
    return channel == 'bi_fast'


def is_rtgs_transfer(txn: Transaction) -> bool:
    """RTGS 채널 여부 (대량 이체)"""
    channel = str(getattr(txn, 'channel', ''))
    return channel == 'rtgs'


def is_rapid_succession(txn: Transaction, threshold: int = None) -> bool:
    """당일 다건 + 금액 anomaly 복합 조건"""
    if threshold is None:
        threshold = get_condition_value("rapid_succession_count", 3)
    return txn.daily_txn_count_today >= threshold and is_amount_anomaly(txn)
