"""
LLM Evaluator: OpenAI GPT-4o로 거래를 평가한다.
당근페이 Step 3 방식: Retrieve + Prompt 구성 + API 호출 (수동 조합)
"""

import json
import logging
import time

from openai import OpenAI

from config import settings
from models.schemas import (
    LLMEvaluation,
    RecommendedAction,
    RiskLevel,
    RuleEngineResult,
    Transaction,
)
from llm.prompts import (
    SYSTEM_PROMPT,
    build_evaluation_prompt,
    format_customer_profile,
    format_transaction_info,
    format_triggered_rules,
)
from llm.rag import format_similar_cases, search_similar_cases

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """LLM 연속 실패 시 자동 차단"""
    def __init__(self, failure_threshold: int = 5, reset_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "closed"

    def can_execute(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            if time.time() - self.last_failure_time >= self.reset_timeout:
                self.state = "half-open"
                return True
            return False
        return True  # half-open

    def record_success(self):
        self.failure_count = 0
        self.state = "closed"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(f"Circuit breaker OPEN after {self.failure_count} failures")


_circuit_breaker = CircuitBreaker()
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


def evaluate_transaction(
    txn: Transaction,
    rule_result: RuleEngineResult,
) -> LLMEvaluation:
    """거래를 LLM으로 평가한다. RAG 검색 → 프롬프트 구성 → API 호출."""

    # 서킷 브레이커 확인
    if not _circuit_breaker.can_execute():
        logger.warning("Circuit breaker open, using fallback")
        return _fallback_evaluation(rule_result)

    # Step 1: RAG - 유사 사기 사례 검색 (풍부한 컨텍스트)
    parts = [f"Transaction type: {txn.transaction_type.value}", f"Amount: {txn.amount:,.0f} IDR"]
    if txn.is_night_transaction:
        parts.append("Night transaction during unusual hours")
    if txn.is_new_device:
        parts.append("New device detected")
    if txn.sim_changed_recently:
        parts.append("SIM card recently changed, possible SIM swap")
    if txn.recipient_type.value == "new":
        parts.append("Transfer to new recipient")
    if txn.recipient_type.value == "blacklisted":
        parts.append("Transfer to blacklisted account")
    if txn.recipient_country != "ID":
        parts.append(f"International transfer to {txn.recipient_country}")
    if txn.sender_account_age_days <= 30:
        parts.append("New account less than 30 days old")
    channel = getattr(txn, 'channel', None)
    if channel:
        parts.append(f"Payment channel: {channel}")
    query_text = ". ".join(parts)

    try:
        similar_cases = search_similar_cases(query_text)
    except Exception as e:
        logger.warning(f"RAG search failed: {e}")
        similar_cases = []

    # Step 2: 프롬프트 구성
    prompt = build_evaluation_prompt(
        transaction_info=format_transaction_info(txn),
        customer_profile=format_customer_profile(txn),
        triggered_rules=format_triggered_rules(rule_result),
        similar_cases=format_similar_cases(similar_cases),
    )

    # Step 3: OpenAI API 호출 (타임아웃 10초)
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=500,
            response_format={"type": "json_object"},
            timeout=10.0,
        )

        content = response.choices[0].message.content
        result = _parse_response(content)
        _circuit_breaker.record_success()
        return result

    except Exception as e:
        _circuit_breaker.record_failure()
        logger.error(f"LLM evaluation failed: {e}")
        return _fallback_evaluation(rule_result)


def _validate_llm_response(data: dict) -> dict:
    """LLM 응답 유효성 검증 및 정규화"""
    data["risk_score"] = max(0, min(100, int(data.get("risk_score", 0))))
    data["confidence"] = max(0, min(100, int(data.get("confidence", 0))))
    valid_levels = {"HIGH", "MEDIUM", "LOW"}
    level = str(data.get("risk_level", "")).upper()
    data["risk_level"] = level if level in valid_levels else "MEDIUM"
    valid_actions = {"BLOCK", "HOLD", "DELAY", "REVIEW", "ALERT", "ALLOW", "ESCALATE"}
    action = str(data.get("recommended_action", "")).upper()
    data["recommended_action"] = action if action in valid_actions else "REVIEW"
    reasoning = str(data.get("reasoning", ""))
    if len(reasoning) > 500:
        data["reasoning"] = reasoning[:497] + "..."
    return data


def _parse_response(content: str) -> LLMEvaluation:
    """LLM 응답을 파싱한다. 실패 시 fallback."""
    try:
        data = json.loads(content)
        data = _validate_llm_response(data)
        return LLMEvaluation(
            risk_level=RiskLevel(data["risk_level"]),
            risk_score=data["risk_score"],
            fraud_type=str(data.get("fraud_type", "")),
            reasoning=str(data.get("reasoning", "")),
            recommended_action=RecommendedAction(data["recommended_action"]),
            confidence=data["confidence"],
            similar_case_match=bool(data.get("similar_case_match", False)),
        )
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.error(f"Failed to parse LLM response: {e}")
        return LLMEvaluation(
            risk_level=RiskLevel.MEDIUM,
            risk_score=50,
            reasoning="LLM 응답 파싱 실패. 수동 검토 필요.",
            recommended_action=RecommendedAction.REVIEW,
            confidence=0,
        )


def _fallback_evaluation(rule_result: RuleEngineResult) -> LLMEvaluation:
    """LLM 호출 실패 시 룰엔진 결과만으로 평가"""
    score = rule_result.risk_score
    if score >= 80:
        level = RiskLevel.HIGH
        action = RecommendedAction.BLOCK
    elif score >= 50:
        level = RiskLevel.MEDIUM
        action = RecommendedAction.REVIEW
    else:
        level = RiskLevel.LOW
        action = RecommendedAction.ALLOW

    rules_desc = ", ".join(r.rule_name for r in rule_result.triggered_rules)
    return LLMEvaluation(
        risk_level=level,
        risk_score=score,
        reasoning=f"Fallback evaluation based on rule engine only. Triggered: {rules_desc}",
        recommended_action=action,
        confidence=30,
    )
