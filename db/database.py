import json
import sqlite3
import time as _time
from contextlib import contextmanager
from datetime import datetime

from config import settings
from models.schemas import (
    DashboardStats,
    FDSResult,
)

# --- TTL 캐시 (거래당 DB 쿼리 최소화) ---
_cache: dict = {}
_CACHE_TTL = 30  # seconds


def _cached_query(key: str, query_fn):
    now = _time.time()
    if key in _cache and now - _cache[key]["ts"] < _CACHE_TTL:
        return _cache[key]["data"]
    data = query_fn()
    _cache[key] = {"data": data, "ts": now}
    return data


def _invalidate_cache():
    """설정 변경 시 캐시 무효화"""
    _cache.clear()

# --- Schema ---

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS fds_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT UNIQUE NOT NULL,
    timestamp TEXT NOT NULL,
    rule_risk_score INTEGER NOT NULL,
    triggered_rules TEXT NOT NULL,
    llm_risk_level TEXT,
    llm_risk_score INTEGER,
    llm_fraud_type TEXT,
    llm_reasoning TEXT,
    llm_confidence INTEGER,
    final_risk_level TEXT NOT NULL,
    final_action TEXT NOT NULL,
    processing_time_ms REAL NOT NULL,
    raw_result TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rule_configs (
    rule_name TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    score INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS condition_params (
    param_name TEXT PRIMARY KEY,
    param_value TEXT NOT NULL,
    description TEXT NOT NULL,
    param_type TEXT NOT NULL DEFAULT 'int',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS policy_configs (
    policy_name TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (policy_name, rule_name)
);

CREATE TABLE IF NOT EXISTS high_risk_countries (
    country_code TEXT PRIMARY KEY,
    country_name TEXT NOT NULL,
    added_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS global_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    record_key TEXT NOT NULL,
    action TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    operator TEXT NOT NULL DEFAULT 'system',
    ip_address TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ppatk_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type TEXT NOT NULL,
    transaction_id TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'IDR',
    risk_level TEXT NOT NULL,
    fraud_type TEXT,
    reasoning TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    submitted_at TEXT
);
"""

# --- Default data (현재 하드코딩 값) ---

DEFAULT_RULES = [
    ("mule_account_suspect", "New account + large transfer + nighttime", 40),
    ("sim_swap_fraud", "SIM change + new device + immediate transfer", 45),
    ("voice_phishing_suspect", "Large amount + new recipient + amount anomaly", 35),
    ("money_laundering_structuring", "Split transactions to avoid reporting", 40),
    ("ppatk_ctr_threshold", "Exceeds PPATK CTR threshold Rp 500 juta", 55),
    ("high_risk_remittance", "International transfer to high-risk country", 45),
    ("blacklisted_recipient", "Blacklisted recipient", 50),
    ("night_large_transfer", "Large nighttime transfer", 20),
    ("abnormal_frequency", "Daily transaction frequency exceeds limit", 25),
    ("amount_anomaly", "Amount far exceeds customer average", 20),
    ("new_device_large_transfer", "New device + large transfer", 25),
    ("repeated_alerts", "Repeated alerts within 30 days", 15),
    ("dormant_account_reactivation", "Dormant account reactivated with large transfer", 40),
    ("account_takeover_suspect", "Limit change + new device + large transfer", 45),
    ("credential_stuffing_ato", "Multiple login attempts + new device", 40),
    ("full_balance_withdrawal", "Near-full balance withdrawal + risk indicator", 45),
    ("bi_fast_rapid_fan_out", "BI-FAST high frequency to new recipients", 40),
    ("ip_mismatch_large_transfer", "IP country mismatch + large transfer", 30),
    ("night_sim_device_combo", "Night + SIM change + new device combo", 50),
]

DEFAULT_CONDITIONS = [
    ("new_account_days", "30", "Max days to consider account as new", "int"),
    ("dormant_days", "180", "Min days for dormant account", "int"),
    ("high_frequency_threshold", "10", "Max daily transactions before flagging", "int"),
    ("large_amount_threshold", "25000000", "Amount (IDR) to consider as large", "float"),
    ("very_large_amount_threshold", "500000000", "PPATK CTR threshold (IDR)", "float"),
    ("amount_anomaly_multiplier", "3.0", "Multiplier vs avg for anomaly", "float"),
    ("split_txn_min_count", "5", "Min daily txn count for split detection", "int"),
    ("recent_alerts_threshold", "2", "Min alerts in 30d to flag", "int"),
    ("login_attempt_threshold", "5", "Max login attempts before flagging", "int"),
    ("rapid_succession_count", "3", "Min txns for rapid succession", "int"),
]

DEFAULT_POLICIES = {
    "domestic_transfer": [
        "mule_account_suspect", "sim_swap_fraud", "voice_phishing_suspect",
        "money_laundering_structuring", "ppatk_ctr_threshold", "blacklisted_recipient",
        "night_large_transfer", "abnormal_frequency", "amount_anomaly",
        "new_device_large_transfer", "repeated_alerts", "dormant_account_reactivation",
        "account_takeover_suspect", "credential_stuffing_ato", "full_balance_withdrawal",
        "bi_fast_rapid_fan_out", "ip_mismatch_large_transfer", "night_sim_device_combo",
    ],
    "international_remittance": [
        "high_risk_remittance", "money_laundering_structuring", "ppatk_ctr_threshold",
        "blacklisted_recipient", "amount_anomaly", "new_device_large_transfer",
        "repeated_alerts", "dormant_account_reactivation",
    ],
}

DEFAULT_COUNTRIES = [
    ("KP", "North Korea"), ("IR", "Iran"), ("MM", "Myanmar"),
    ("AF", "Afghanistan"), ("SY", "Syria"), ("YE", "Yemen"),
    ("SO", "Somalia"), ("LY", "Libya"),
]

DEFAULT_SETTINGS = [
    ("llm_threshold", "50", "Rule score threshold to invoke LLM"),
    ("block_threshold", "80", "Rule score threshold for auto-block"),
    ("rag_top_k", "3", "Number of similar cases to retrieve"),
]


# --- Connection ---

@contextmanager
def _get_conn():
    conn = sqlite3.connect(settings.sqlite_db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# --- Init ---

def init_db():
    with _get_conn() as conn:
        conn.executescript(SCHEMA_SQL)
        _seed_defaults(conn)


def _seed_defaults(conn):
    """하드코딩 기본값을 DB에 시딩 (이미 있으면 스킵)"""
    for name, desc, score in DEFAULT_RULES:
        conn.execute(
            "INSERT OR IGNORE INTO rule_configs (rule_name, description, score) VALUES (?, ?, ?)",
            (name, desc, score),
        )
    for name, val, desc, ptype in DEFAULT_CONDITIONS:
        conn.execute(
            "INSERT OR IGNORE INTO condition_params (param_name, param_value, description, param_type) VALUES (?, ?, ?, ?)",
            (name, val, desc, ptype),
        )
    for policy, rules in DEFAULT_POLICIES.items():
        for rule in rules:
            conn.execute(
                "INSERT OR IGNORE INTO policy_configs (policy_name, rule_name) VALUES (?, ?)",
                (policy, rule),
            )
    for code, name in DEFAULT_COUNTRIES:
        conn.execute(
            "INSERT OR IGNORE INTO high_risk_countries (country_code, country_name) VALUES (?, ?)",
            (code, name),
        )
    for key, val, desc in DEFAULT_SETTINGS:
        conn.execute(
            "INSERT OR IGNORE INTO global_settings (key, value, description) VALUES (?, ?, ?)",
            (key, val, desc),
        )


# --- Audit Log ---

def _log_change(conn, table: str, key: str, action: str, old_val, new_val, operator: str = "system", ip_address: str = None):
    conn.execute(
        "INSERT INTO audit_log (table_name, record_key, action, old_value, new_value, operator, ip_address) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (table, key, action, json.dumps(old_val) if old_val else None, json.dumps(new_val) if new_val else None, operator, ip_address),
    )


# --- FDS Results ---

def save_result(result: FDSResult):
    with _get_conn() as conn:
        llm = result.llm_evaluation
        conn.execute(
            """INSERT OR REPLACE INTO fds_results
            (transaction_id, timestamp, rule_risk_score, triggered_rules,
             llm_risk_level, llm_risk_score, llm_fraud_type, llm_reasoning,
             llm_confidence, final_risk_level, final_action,
             processing_time_ms, raw_result)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result.transaction_id,
                result.timestamp.isoformat(),
                result.rule_engine_result.risk_score,
                json.dumps([r.model_dump() for r in result.rule_engine_result.triggered_rules]),
                llm.risk_level.value if llm else None,
                llm.risk_score if llm else None,
                llm.fraud_type if llm else None,
                llm.reasoning if llm else None,
                llm.confidence if llm else None,
                result.final_risk_level.value,
                result.final_action.value,
                result.processing_time_ms,
                result.model_dump_json(),
            ),
        )


def get_results(limit: int = 50, offset: int = 0, risk_level: str = None) -> list[dict]:
    with _get_conn() as conn:
        query = "SELECT * FROM fds_results"
        params = []
        if risk_level:
            query += " WHERE final_risk_level = ?"
            params.append(risk_level)
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_stats() -> DashboardStats:
    with _get_conn() as conn:
        row = conn.execute(
            """SELECT
                COUNT(*) as total,
                SUM(CASE WHEN final_risk_level='HIGH' THEN 1 ELSE 0 END) as high,
                SUM(CASE WHEN final_risk_level='MEDIUM' THEN 1 ELSE 0 END) as medium,
                SUM(CASE WHEN final_risk_level='LOW' THEN 1 ELSE 0 END) as low,
                SUM(CASE WHEN final_action='BLOCK' THEN 1 ELSE 0 END) as blocked,
                SUM(CASE WHEN final_action='REVIEW' THEN 1 ELSE 0 END) as review,
                AVG(processing_time_ms) as avg_time
            FROM fds_results"""
        ).fetchone()

        fraud_rows = conn.execute(
            """SELECT llm_fraud_type, COUNT(*) as cnt
            FROM fds_results WHERE llm_fraud_type IS NOT NULL AND llm_fraud_type != ''
            GROUP BY llm_fraud_type"""
        ).fetchall()

        return DashboardStats(
            total_transactions=row["total"] or 0,
            high_risk_count=row["high"] or 0,
            medium_risk_count=row["medium"] or 0,
            low_risk_count=row["low"] or 0,
            blocked_count=row["blocked"] or 0,
            review_count=row["review"] or 0,
            avg_processing_time_ms=row["avg_time"] or 0,
            fraud_type_distribution={r["llm_fraud_type"]: r["cnt"] for r in fraud_rows},
        )


# --- Rule Configs ---

def get_rule_configs() -> list[dict]:
    def _query():
        with _get_conn() as conn:
            rows = conn.execute("SELECT * FROM rule_configs ORDER BY rule_name").fetchall()
            return [dict(r) for r in rows]
    return _cached_query("rule_configs", _query)


def update_rule_config(rule_name: str, score: int = None, enabled: bool = None, operator: str = "system"):
    _invalidate_cache()
    with _get_conn() as conn:
        old = conn.execute("SELECT * FROM rule_configs WHERE rule_name = ?", (rule_name,)).fetchone()
        if not old:
            return False
        old_dict = dict(old)
        if score is not None:
            conn.execute(
                "UPDATE rule_configs SET score = ?, updated_at = datetime('now') WHERE rule_name = ?",
                (score, rule_name),
            )
        if enabled is not None:
            conn.execute(
                "UPDATE rule_configs SET enabled = ?, updated_at = datetime('now') WHERE rule_name = ?",
                (1 if enabled else 0, rule_name),
            )
        new = conn.execute("SELECT * FROM rule_configs WHERE rule_name = ?", (rule_name,)).fetchone()
        _log_change(conn, "rule_configs", rule_name, "update", old_dict, dict(new))
        return True


# --- Condition Params ---

def get_condition_params() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM condition_params ORDER BY param_name").fetchall()
        return [dict(r) for r in rows]


def update_condition_param(param_name: str, param_value: str, operator: str = "system"):
    _invalidate_cache()
    with _get_conn() as conn:
        old = conn.execute("SELECT * FROM condition_params WHERE param_name = ?", (param_name,)).fetchone()
        if not old:
            return False
        _log_change(conn, "condition_params", param_name, "update", dict(old), {"param_value": param_value})
        conn.execute(
            "UPDATE condition_params SET param_value = ?, updated_at = datetime('now') WHERE param_name = ?",
            (param_value, param_name),
        )
        return True


def get_condition_value(param_name: str, default):
    """룰엔진에서 호출: DB에서 조건 파라미터 값을 가져온다. (캐싱 적용)"""
    def _query():
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT param_value, param_type FROM condition_params WHERE param_name = ?",
                (param_name,),
            ).fetchone()
            if not row:
                return default
            val, ptype = row["param_value"], row["param_type"]
            if ptype == "int":
                return int(val)
            elif ptype == "float":
                return float(val)
            return val
    return _cached_query(f"cond:{param_name}", _query)


# --- Policy Configs ---

def get_policy_configs() -> dict[str, list[dict]]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT pc.*, rc.description, rc.score, rc.enabled as rule_enabled "
            "FROM policy_configs pc "
            "LEFT JOIN rule_configs rc ON pc.rule_name = rc.rule_name "
            "ORDER BY pc.policy_name, pc.rule_name"
        ).fetchall()
        policies: dict[str, list[dict]] = {}
        for r in rows:
            d = dict(r)
            policies.setdefault(d["policy_name"], []).append(d)
        return policies


def get_policy_rule_names(policy_name: str) -> list[str]:
    """룰엔진에서 호출: 정책에 활성화된 규칙 이름 목록 (캐싱 적용)"""
    def _query():
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT pc.rule_name FROM policy_configs pc "
                "JOIN rule_configs rc ON pc.rule_name = rc.rule_name "
                "WHERE pc.policy_name = ? AND pc.enabled = 1 AND rc.enabled = 1",
                (policy_name,),
            ).fetchall()
            return [r["rule_name"] for r in rows]
    return _cached_query(f"policy:{policy_name}", _query)


def update_policy_rule(policy_name: str, rule_name: str, enabled: bool, operator: str = "system"):
    _invalidate_cache()
    with _get_conn() as conn:
        conn.execute(
            "UPDATE policy_configs SET enabled = ? WHERE policy_name = ? AND rule_name = ?",
            (1 if enabled else 0, policy_name, rule_name),
        )
        _log_change(conn, "policy_configs", f"{policy_name}/{rule_name}", "update", None, {"enabled": enabled})


def add_policy_rule(policy_name: str, rule_name: str):
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO policy_configs (policy_name, rule_name) VALUES (?, ?)",
            (policy_name, rule_name),
        )
        _log_change(conn, "policy_configs", f"{policy_name}/{rule_name}", "add", None, None)


# --- High Risk Countries ---

def get_high_risk_countries() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM high_risk_countries ORDER BY country_code").fetchall()
        return [dict(r) for r in rows]


def get_high_risk_country_codes() -> set[str]:
    """룰엔진에서 호출 (캐싱 적용)"""
    def _query():
        with _get_conn() as conn:
            rows = conn.execute("SELECT country_code FROM high_risk_countries").fetchall()
            return {r["country_code"] for r in rows}
    return _cached_query("high_risk_countries", _query)


def add_high_risk_country(code: str, name: str, operator: str = "system"):
    _invalidate_cache()
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO high_risk_countries (country_code, country_name) VALUES (?, ?)",
            (code.upper(), name),
        )
        _log_change(conn, "high_risk_countries", code.upper(), "add", None, {"code": code, "name": name})


def remove_high_risk_country(code: str, operator: str = "system"):
    _invalidate_cache()
    with _get_conn() as conn:
        conn.execute("DELETE FROM high_risk_countries WHERE country_code = ?", (code.upper(),))
        _log_change(conn, "high_risk_countries", code.upper(), "delete", {"code": code}, None)


# --- Global Settings ---

def get_global_settings() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM global_settings ORDER BY key").fetchall()
        return [dict(r) for r in rows]


def get_setting(key: str, default: str = "") -> str:
    def _query():
        with _get_conn() as conn:
            row = conn.execute("SELECT value FROM global_settings WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default
    return _cached_query(f"setting:{key}", _query)


def update_setting(key: str, value: str, operator: str = "system"):
    _invalidate_cache()
    with _get_conn() as conn:
        old = conn.execute("SELECT value FROM global_settings WHERE key = ?", (key,)).fetchone()
        conn.execute(
            "UPDATE global_settings SET value = ?, updated_at = datetime('now') WHERE key = ?",
            (value, key),
        )
        _log_change(conn, "global_settings", key, "update", dict(old) if old else None, {"value": value})


# --- Audit Log ---

def get_audit_log(limit: int = 100) -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


# --- PPATK Reports ---

def save_ppatk_report(report) -> int:
    """PPATK 보고서 저장"""
    with _get_conn() as conn:
        cursor = conn.execute(
            """INSERT INTO ppatk_reports
            (report_type, transaction_id, amount, currency, risk_level, fraud_type, reasoning, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                report.report_type.value if hasattr(report.report_type, "value") else report.report_type,
                report.transaction_id,
                report.amount,
                report.currency,
                report.risk_level.value if hasattr(report.risk_level, "value") else report.risk_level,
                report.fraud_type,
                report.reasoning,
                report.status,
            ),
        )
        return cursor.lastrowid


def get_ppatk_reports(limit: int = 50, status: str = None) -> list[dict]:
    """PPATK 보고서 목록 조회"""
    with _get_conn() as conn:
        query = "SELECT * FROM ppatk_reports"
        params = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def update_ppatk_report_status(report_id: int, status: str, operator: str = "system"):
    """PPATK 보고서 상태 업데이트"""
    with _get_conn() as conn:
        submitted = datetime.now().isoformat() if status == "submitted" else None
        conn.execute(
            "UPDATE ppatk_reports SET status = ?, submitted_at = COALESCE(?, submitted_at) WHERE id = ?",
            (status, submitted, report_id),
        )
        _log_change(conn, "ppatk_reports", str(report_id), "status_update", None, {"status": status}, operator)
