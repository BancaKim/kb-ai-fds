# KB Indonesia AI FDS PoC — 비즈니스 로직 종합 리뷰 보고서

> **리뷰 일자**: 2026-04-03
> **리뷰 팀**: 인도네시아 감독당국 전문가, FDS 도메인 전문가, 은행 업무/운영 전문가

---

## Executive Summary

| 전문가 | 종합 등급 | 핵심 판단 |
|--------|----------|----------|
| 🏛️ **인도네시아 규제 전문가** | ⚠️ PARTIALLY COMPLIANT | CTR 거래유형 미구분, UU PDP 위반(OpenAI PII 전송), BI 결제채널 미분화, PEP/제재 미구현 |
| 🔍 **FDS 전문가** | ⚠️ WEAK | LLM이 HIGH 거래를 ALLOW로 오버라이드 가능(치명적), 규칙 12개로 커버리지 부족, 스코어링 중복 문제 |
| 🏦 **은행 운영 전문가** | 🔴 NOT READY | 케이스 관리 전무, 고객 통지 없음, PPATK 보고 미구현, 업무 연속성 미대응 |

**PoC 기술 시연용으로는 적절하나, 파일럿/운영 전환 전 비즈니스 로직 전반에 걸쳐 심각한 보완 필요.**

---

## 1. 🔴 즉시 조치 (3개 전문가 공통 지적)

### 1.1 LLM 오버라이드 안전장치 부재 (FDS 전문가 — CRITICAL)

**현재 문제**: `api/routes.py:191-206`에서 LLM 결과가 있으면 **무조건** LLM 판단을 최종 결과로 사용.

```
룰엔진: blacklisted_recipient(50) + amount_anomaly(20) + night_large(20) = 90점 → HIGH/BLOCK
LLM: hallucination → LOW/ALLOW
최종 결과: ALLOW ← 블랙리스트 수취인에게 야간 대량이체가 승인됨
```

**권고**:
- 룰엔진 score >= 80이면 LLM이 de-escalate 불가
- `blacklisted_recipient` 트리거 시 LLM ALLOW 금지
- LLM confidence < 50이면 룰엔진 판단 유지

### 1.2 PPATK CTR 점수 부족 (규제 전문가 + FDS 전문가)

**현재**: `ppatk_ctr_threshold` 규칙이 **25점**으로 LLM 호출 임계값(50)에도 미달.
5억 IDR 이상 거래가 점수 25점만 받아 **규제 보고 대상 거래가 충분한 심사를 받지 못함**.

**권고**: 최소 50점 이상으로 상향 (LLM 호출 보장)

### 1.3 `is_dormant_reactivated` 미사용 (FDS 전문가)

**현재**: `conditions.py:18-21`에 휴면계좌 재활성화 함수가 정의되어 있으나 **어떤 규칙에서도 사용하지 않음**. fraud case `case_002.json`이 정확히 이 패턴인데 탐지 불가.

---

## 2. 🏛️ 인도네시아 규제 준수 현황

| 규제 영역 | 등급 | 핵심 결함 |
|-----------|------|----------|
| **PPATK (CTR/STR)** | PARTIALLY COMPLIANT | CTR이 현금/전자 미구분, goAML 미연동, LTKM 자동 생성 없음, 다일 구조화 미탐지 |
| **OJK (FDS/MRM)** | PARTIALLY COMPLIANT | 코어뱅킹 차단 연동 없음, MRM 프레임워크 없음, 감사로그에 변경자 미기록 |
| **BI 결제시스템** | 🔴 NON-COMPLIANT | BI-FAST/SKNBI/RTGS/QRIS 채널 **전혀 미분화** |
| **UU PDP 개인정보** | 🔴 NON-COMPLIANT | PII 마스킹 미구현, 미국 OpenAI 서버 전송 (데이터 거주성 위반) |
| **PEP/제재/CDD** | NOT ADDRESSED | PEP 심사, DTTOT/UN/OFAC 제재 목록, CDD/EDD 연동, FATF Rec.16 **전부 미구현** |
| **Fraud Case KB** | ✅ COMPLIANT | 12건 현실적, IDR 금액 적절, 다만 pinjol/QRIS/BEC 등 8개 유형 추가 필요 |

### 주요 규제 리스크

1. **BI 결제채널**: `TransactionType`에 BI-FAST/RTGS/SKNBI/QRIS가 없어 채널별 위험 프로파일링 불가. fraud case에서 BI-FAST, RTGS가 명시적으로 언급되는데 시스템은 구분 못함.

2. **UU PDP 위반**: 계획서에서 PII 마스킹 전략을 상세히 기술했으나 코드에는 **마스킹 로직이 전혀 없음**. OpenAI API로 거래 데이터가 미국 서버에 전송됨.

3. **누적 구조화**: 동일 송금인→수취인 간 multi-day 분산이체 탐지 불가. `daily_txn_count_today` 기반이라 2~3일 걸친 회피 패턴 놓침.

---

## 3. 🔍 FDS 탐지 효과성 분석

### 3.1 탐지 갭 (놓치는 사기)

| 시나리오 | 왜 놓치는가 | 심각도 |
|---------|-----------|--------|
| **저속 Romance Scam** | 월 1~2회 3~5M IDR — 어떤 규칙도 미트리거 | 높음 |
| **OJK 임계값 직하 분할** | 49.5M IDR × 3건 — large_amount 미달, split_txn 건수 미달 | 높음 |
| **Credential Stuffing ATO** | case_010에 사례 있으나 전용 규칙 없음 | 높음 |
| **주간 정상 위장 사기** | 업무시간+기존 디바이스+기존 수취인+49M — 규칙 0개 트리거 | 높음 |

### 3.2 오탐 위험 (정상을 차단)

| 시나리오 | 왜 오탐인가 | 영향 |
|---------|-----------|------|
| **기업 급여 일괄지급** | 50명 급여 → frequency(25) + anomaly(20) = 45점 | 고객 이탈 |
| **라마단/르바란 THR 보너스** | 평소 5~10배 거래 증가는 정상. 시즌 보정 없음 | 대량 오탐 |
| **UMKM 일일 다건 거래** | 소상공인 일 20건+ 정상 — frequency 트리거 | 고객 불만 |

### 3.3 스코어링 모델 문제

**중복 카운팅**: SIM swap 거래가 `sim_swap_fraud`(45) + `new_device_large`(25) + `amount_anomaly`(20) + `night_large`(20) = 110점. 동일 위험 지표가 여러 규칙에서 중복 계산됨.

**권고**: 카테고리별 max + 카테고리간 합산 방식, 또는 상관 규칙 중복 할인(discount factor) 도입.

### 3.4 임계값 조정 필요

| 파라미터 | 현재값 | 권고값 | 근거 |
|---------|--------|--------|------|
| high_frequency_threshold | 20건/일 | **10건/일** | 인도네시아 개인 평균 일 5~10건 |
| large_amount_threshold | 50M IDR | **25M IDR** | 중산층 월급 5~15M 기준 |
| amount_anomaly_multiplier | 5.0배 | **3.0배** | 업계 표준 |
| ppatk_ctr_threshold score | 25점 | **50점+** | 규제 보고 대상 LLM 심사 보장 |

---

## 4. 🏦 은행 운영 준비도

### 4.1 부재한 핵심 업무 프로세스

| 프로세스 | 현재 상태 | 필요 사유 |
|---------|----------|----------|
| **케이스 관리 큐** | 없음 | 분석가에게 alert 배정/조사/종결 워크플로우 필수 |
| **TP/FP 마킹** | 없음 | 탐지 정확도 측정 불가, 피드백 루프 불가 |
| **고객 통지** | 없음 | OJK 규정상 차단 시 고객 즉시 통지 의무 |
| **HOLD vs BLOCK 구분** | 없음 | 임시보류(분석가 확인 후 해제) vs 영구차단 구분 필수 |
| **이의 제기 프로세스** | 없음 | 오탐된 고객의 해제 요청 처리 경로 필요 |
| **Maker-Checker** | 없음 | 규칙 변경 시 복수 승인 필수 (현재 즉시 적용) |
| **에스컬레이션** | 없음 | 상위 관리자/컴플라이언스 이관 경로 |
| **근무 교대 인계** | 없음 | 미완료 케이스 담당자 이관 |

### 4.2 코어뱅킹 연동 필수 필드

현재 Transaction 모델에 **누락된** 코어뱅킹 필수 필드:

| 필드 | 중요도 | 출처 |
|------|--------|------|
| `channel` (mobile/internet/ATM/BI-FAST/RTGS) | Critical | T24: CHANNEL.ID |
| `sender_name`, `sender_cif` | Critical | 고객 식별 |
| `recipient_bank_code` | Critical | 네오뱅크 목적지 리스크 판단 |
| `account_balance_before` | High | 전액 인출 패턴 탐지 |
| `transaction_purpose` | High | BI 해외송금 요건 |
| `auth_method` (OTP/biometric/PIN) | High | 인증 방식별 리스크 |
| `limit_recently_changed` | Critical | ATO 탐지 핵심 지표 |

### 4.3 비용 추정

| 항목 | 월간 추정 |
|------|----------|
| OpenAI GPT-4o API (일 50K~100K 거래 기준) | **$1,300 ~ $5,200** |
| GPT-4o-mini 전환 시 | ~$130 ~ $520 (1/10) |
| 분석가 인력 (10~50명, 3교대) | 운영 비용 주요 항목 |
| 인프라 (PostgreSQL, Redis, 네트워크) | 별도 산정 필요 |

---

## 5. 프로덕션 전환 우선순위 로드맵

### Phase 1: 즉시 수정 (1~2주)

| # | 작업 | 공수 | 담당 |
|---|------|------|------|
| 1 | LLM 오버라이드 안전장치 구현 | Low | 개발 |
| 2 | `ppatk_ctr_threshold` 점수 50점 이상 상향 | Low | FDS 운영 |
| 3 | `is_dormant_reactivated` 규칙 활성화 | Low | 개발 |
| 4 | 임계값 현실화 (frequency 10, amount 25M, anomaly 3.0x) | Low | FDS 운영 |
| 5 | PII 마스킹 레이어 구현 (LLM 전달 전) | Medium | 개발 |

### Phase 2: 규제 필수 (1~2개월)

| # | 작업 | 공수 | 담당 |
|---|------|------|------|
| 6 | BI-FAST/SKNBI/RTGS/QRIS 채널 분화 | Medium | 개발 |
| 7 | PPATK LTKM/LTKT 자동 보고 모듈 | High | 컴플라이언스+개발 |
| 8 | Transaction 모델 필수 필드 확장 | Medium | 개발 |
| 9 | 감사 로그 강화 (변경자, LLM 전문, 5년 보존) | Low | 개발 |
| 10 | PEP/제재 목록 연동 인터페이스 | Medium | 컴플라이언스+개발 |

### Phase 3: 운영 필수 (2~3개월)

| # | 작업 | 공수 | 담당 |
|---|------|------|------|
| 11 | 케이스 관리 시스템 (큐/배정/조사/종결) | High | 개발 |
| 12 | TP/FP 마킹 + 피드백 루프 | Medium | FDS 운영+개발 |
| 13 | 고객 통지 + HOLD/BLOCK/DELAY 액션 분화 | Medium | 개발+고객서비스 |
| 14 | Maker-Checker 규칙 변경 프로세스 | Medium | 개발 |
| 15 | RBAC (역할별 접근 권한) | Medium | 보안+개발 |

### Phase 4: 고도화 (3~6개월)

| # | 작업 | 공수 | 담당 |
|---|------|------|------|
| 16 | 시간 윈도우 기반 프로파일링 (1h/4h/24h/7d/30d) | High | 개발 |
| 17 | 누락 규칙 추가 (ATO, structuring, neobank 등 5개+) | Medium | FDS 운영 |
| 18 | 스코어링 모델 개선 (카테고리별 max + 합산) | Medium | FDS 운영+개발 |
| 19 | 전통 ML 모델 도입 (XGBoost) + LLM은 설명 생성에 한정 | High | 데이터사이언스 |
| 20 | 네트워크 분석 (계좌간 자금흐름 그래프) | Very High | 데이터사이언스 |

---

## 6. PoC 강점 (3개 전문가 공통 인정)

| 항목 | 내용 |
|------|------|
| **당근페이 패턴 충실 구현** | Condition → Rule → Policy 3계층, XML 프롬프트, 수동 RAG 파이프라인 |
| **Fraud Case KB 품질** | 12건 인도네시아 현실적 사례 (BRI, BCA, Mandiri, BI-FAST, RTGS 등 현지 은행/결제 반영) |
| **동적 규칙 관리** | DB 기반 실시간 점수/임계값/정책 조정 + 감사 로그 |
| **비용 최적화** | 룰엔진 1차 필터링으로 LLM 호출 최소화 (10건 중 1~2건만) |
| **LLM Fallback** | OpenAI 장애 시 룰엔진 단독 판정으로 대체 |
| **LLM 설명가능성** | reasoning 필드로 판단 근거 제공 — OJK AI 설명가능성 요건 기초 충족 |
