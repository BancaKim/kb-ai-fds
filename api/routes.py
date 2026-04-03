"""
FastAPI 라우트: FDS 평가 + 관리 API
"""

import time
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from models.schemas import (
    DashboardStats,
    EvaluateRequest,
    EvaluateResponse,
    FDSResult,
    RecommendedAction,
    RiskLevel,
    Transaction,
)
from rule_engine.engine import evaluate as rule_evaluate
from llm.evaluator import evaluate_transaction as llm_evaluate
from db import database as db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


# ========== RBAC (역할 기반 접근 제어) ==========

VALID_ROLES = {"admin", "analyst", "viewer"}


def _get_role(request: Request) -> str:
    role = request.headers.get("X-API-Role", "viewer").lower()
    return role if role in VALID_ROLES else "viewer"


def _get_operator(request: Request) -> str:
    return request.headers.get("X-API-Operator", "system")


def require_admin(request: Request):
    if _get_role(request) != "admin":
        raise HTTPException(403, "Admin role required")


def require_analyst(request: Request):
    if _get_role(request) not in ("admin", "analyst"):
        raise HTTPException(403, "Analyst or admin role required")


def require_viewer(request: Request):
    pass  # 모든 역할 허용


# ========== Transaction Evaluation ==========

@router.post("/transactions/evaluate", response_model=EvaluateResponse)
def evaluate_transaction(request: EvaluateRequest, _=Depends(require_analyst)):
    start = time.time()
    txn = request.transaction

    if not txn.transaction_id:
        txn.transaction_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"

    rule_result = rule_evaluate(txn)

    llm_result = None
    if rule_result.should_invoke_llm:
        llm_result = llm_evaluate(txn, rule_result)

    final_risk, final_action = _determine_final_result(rule_result, llm_result)
    elapsed_ms = (time.time() - start) * 1000

    result = FDSResult(
        transaction_id=txn.transaction_id,
        rule_engine_result=rule_result,
        llm_evaluation=llm_result,
        final_risk_level=final_risk,
        final_action=final_action,
        processing_time_ms=round(elapsed_ms, 1),
    )

    try:
        db.save_result(result)
    except Exception as e:
        logger.error(f"Failed to save result: {e}")

    return EvaluateResponse(success=True, result=result)


@router.post("/transactions/batch", response_model=list[EvaluateResponse])
def evaluate_batch(transactions: list[Transaction], _=Depends(require_analyst)):
    if len(transactions) > 100:
        raise HTTPException(400, "Batch size cannot exceed 100 transactions")
    return [
        evaluate_transaction(EvaluateRequest(transaction=txn))
        for txn in transactions
    ]


@router.get("/transactions")
def list_transactions(limit: int = 50, offset: int = 0, risk_level: str = None):
    return db.get_results(limit=limit, offset=offset, risk_level=risk_level)


@router.get("/dashboard/stats", response_model=DashboardStats)
def dashboard_stats():
    return db.get_stats()


# ========== Rule Management ==========

class RuleUpdate(BaseModel):
    score: Optional[int] = None
    enabled: Optional[bool] = None


@router.get("/rules")
def get_rules():
    return db.get_rule_configs()


@router.put("/rules/{rule_name}")
def update_rule(rule_name: str, body: RuleUpdate, request: Request, _=Depends(require_admin)):
    operator = _get_operator(request)
    logger.info(f"Rule update by {operator}: {rule_name}")
    ok = db.update_rule_config(rule_name, score=body.score, enabled=body.enabled, operator=operator)
    if not ok:
        raise HTTPException(404, f"Rule '{rule_name}' not found")
    return {"status": "updated", "rule_name": rule_name}


# ========== Condition Parameters ==========

class ConditionUpdate(BaseModel):
    param_value: str


@router.get("/conditions")
def get_conditions():
    return db.get_condition_params()


@router.put("/conditions/{param_name}")
def update_condition(param_name: str, body: ConditionUpdate, request: Request, _=Depends(require_admin)):
    operator = _get_operator(request)
    logger.info(f"Condition update by {operator}: {param_name}")
    ok = db.update_condition_param(param_name, body.param_value, operator=operator)
    if not ok:
        raise HTTPException(404, f"Condition '{param_name}' not found")
    return {"status": "updated", "param_name": param_name}


# ========== Policy Management ==========

class PolicyRuleUpdate(BaseModel):
    enabled: bool


@router.get("/policies")
def get_policies():
    return db.get_policy_configs()


@router.put("/policies/{policy_name}/rules/{rule_name}")
def update_policy_rule(policy_name: str, rule_name: str, body: PolicyRuleUpdate):
    db.update_policy_rule(policy_name, rule_name, body.enabled)
    return {"status": "updated"}


# ========== High Risk Countries ==========

class CountryAdd(BaseModel):
    country_code: str
    country_name: str


@router.get("/countries")
def get_countries():
    return db.get_high_risk_countries()


@router.post("/countries")
def add_country(body: CountryAdd):
    db.add_high_risk_country(body.country_code, body.country_name)
    return {"status": "added", "country_code": body.country_code}


@router.delete("/countries/{code}")
def remove_country(code: str):
    db.remove_high_risk_country(code)
    return {"status": "removed", "country_code": code}


# ========== Global Settings ==========

class SettingUpdate(BaseModel):
    value: str


@router.get("/settings")
def get_settings():
    return db.get_global_settings()


@router.put("/settings/{key}")
def update_setting_endpoint(key: str, body: SettingUpdate, request: Request, _=Depends(require_admin)):
    operator = _get_operator(request)
    logger.info(f"Setting update by {operator}: {key}")
    db.update_setting(key, body.value, operator=operator)
    return {"status": "updated", "key": key}


# ========== Audit Log ==========

@router.get("/audit-log")
def get_audit_log(limit: int = 100):
    return db.get_audit_log(limit=limit)


# ========== Helpers ==========

FORCE_BLOCK_RULES = {"blacklisted_recipient", "high_risk_remittance"}


def _determine_final_result(rule_result, llm_result):
    block_threshold = int(db.get_setting("block_threshold", "80"))
    llm_threshold = int(db.get_setting("llm_threshold", "50"))

    triggered_names = {r.rule_name for r in rule_result.triggered_rules}

    # Safety Guard 1: 강제 차단 규칙은 LLM이 오버라이드 불가
    if triggered_names & FORCE_BLOCK_RULES:
        return RiskLevel.HIGH, RecommendedAction.BLOCK

    # Safety Guard 2: 룰엔진 score >= block_threshold이면 LLM이 de-escalate 불가
    if rule_result.risk_score >= block_threshold:
        if llm_result and llm_result.risk_level == RiskLevel.HIGH:
            return llm_result.risk_level, llm_result.recommended_action
        return RiskLevel.HIGH, RecommendedAction.BLOCK

    # Safety Guard 3: LLM confidence가 낮으면 룰엔진 판단 우선
    if llm_result and llm_result.confidence >= 50:
        return llm_result.risk_level, llm_result.recommended_action

    # LLM 결과가 있지만 confidence 낮으면 룰엔진 기준으로 판정
    score = rule_result.risk_score
    if score >= llm_threshold:
        return RiskLevel.MEDIUM, RecommendedAction.REVIEW
    elif score > 0:
        return RiskLevel.LOW, RecommendedAction.ALERT
    else:
        return RiskLevel.LOW, RecommendedAction.ALLOW
