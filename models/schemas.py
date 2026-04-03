from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --- Enums ---

class TransactionType(str, Enum):
    DOMESTIC_TRANSFER = "domestic_transfer"
    INTERBANK_TRANSFER = "interbank_transfer"
    INTERNATIONAL_REMITTANCE = "international_remittance"


# 결제 채널 — BI-FAST/RTGS/SKNBI/QRIS 등 인도네시아 결제 인프라 구분
class PaymentChannel(str, Enum):
    BI_FAST = "bi_fast"
    RTGS = "rtgs"
    SKNBI = "sknbi"
    QRIS = "qris"
    INTERNAL = "internal"
    SWIFT = "swift"
    MOBILE_BANKING = "mobile_banking"
    INTERNET_BANKING = "internet_banking"
    ATM = "atm"
    BRANCH = "branch"


class RiskLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RecommendedAction(str, Enum):
    BLOCK = "BLOCK"       # 즉시 차단 (영구)
    HOLD = "HOLD"         # 임시 보류 (분석가 확인 후 해제)
    DELAY = "DELAY"       # 지연 처리
    REVIEW = "REVIEW"     # 수동 검토 필요
    ALERT = "ALERT"       # 경보만 (거래 허용)
    ALLOW = "ALLOW"       # 정상 허용
    ESCALATE = "ESCALATE" # 상위 관리자 이관


class RecipientType(str, Enum):
    NEW = "new"
    EXISTING = "existing"
    BLACKLISTED = "blacklisted"


# --- Transaction ---

class Transaction(BaseModel):
    transaction_id: str = Field(default_factory=lambda: "")
    transaction_type: TransactionType
    amount: float = Field(gt=0, le=100_000_000_000)
    currency: str = "IDR"
    timestamp: datetime = Field(default_factory=datetime.now)
    sender_account_id: str
    sender_account_age_days: int
    recipient_account_id: str
    recipient_type: RecipientType = RecipientType.EXISTING
    recipient_country: str = "ID"
    device_id: str = ""
    ip_address: str = ""
    is_night_transaction: bool = False
    sim_changed_recently: bool = False
    is_new_device: bool = False
    memo: str = ""

    # 결제 채널 (BI-FAST/RTGS/SKNBI/QRIS 등)
    channel: PaymentChannel = PaymentChannel.MOBILE_BANKING

    # 발신자 확장
    sender_name: str = ""
    sender_cif: str = ""

    # 수취인 확장
    recipient_bank_code: str = ""
    recipient_name: str = ""

    # 잔액/인증
    account_balance_before: float = 0
    transaction_purpose: str = ""
    auth_method: str = "otp"
    limit_recently_changed: bool = False
    is_full_balance_withdrawal: bool = False
    login_attempts_today: int = 0
    ip_country: str = "ID"

    # Customer profile
    avg_monthly_txn_count: int = 10
    avg_transaction_amount: float = 5_000_000
    usual_transaction_hours: str = "09:00-18:00"
    recent_alerts_30d: int = 0
    daily_txn_count_today: int = 1
    daily_amount_today: float = 0


# --- Rule Engine Result ---

class TriggeredRule(BaseModel):
    rule_name: str
    description: str
    score: int


class RuleEngineResult(BaseModel):
    risk_score: int = 0
    triggered_rules: list[TriggeredRule] = []
    should_invoke_llm: bool = False
    policy_name: str = ""


# --- LLM Evaluation ---

class LLMEvaluation(BaseModel):
    risk_level: RiskLevel = RiskLevel.LOW
    risk_score: int = 0
    fraud_type: str = ""
    reasoning: str = ""
    recommended_action: RecommendedAction = RecommendedAction.ALLOW
    confidence: int = 0
    similar_case_match: bool = False


# --- Combined FDS Result ---

class FDSResult(BaseModel):
    transaction_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    rule_engine_result: RuleEngineResult
    llm_evaluation: Optional[LLMEvaluation] = None
    final_risk_level: RiskLevel
    final_action: RecommendedAction
    processing_time_ms: float = 0


# --- API Request/Response ---

class EvaluateRequest(BaseModel):
    transaction: Transaction


class EvaluateResponse(BaseModel):
    success: bool = True
    result: FDSResult


class DashboardStats(BaseModel):
    total_transactions: int = 0
    high_risk_count: int = 0
    medium_risk_count: int = 0
    low_risk_count: int = 0
    blocked_count: int = 0
    review_count: int = 0
    avg_processing_time_ms: float = 0
    fraud_type_distribution: dict[str, int] = {}


# --- PPATK 보고 모델 ---

class PPATKReportType(str, Enum):
    LTKM = "LTKM"  # 현금거래보고 (Cash Transaction Report)
    LTKT = "LTKT"   # 의심거래보고 (Suspicious Transaction Report)


class PPATKReport(BaseModel):
    report_type: PPATKReportType
    transaction_id: str
    report_date: datetime = Field(default_factory=datetime.now)
    amount: float
    currency: str = "IDR"
    risk_level: RiskLevel
    fraud_type: str = ""
    reasoning: str = ""
    status: str = "pending"  # pending, submitted, confirmed
