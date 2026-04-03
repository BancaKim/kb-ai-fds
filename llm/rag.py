"""
RAG: ChromaDB 기반 유사 사기 사례 검색
당근페이 교훈: 1건 = 1 JSON 파일, 도메인별 분리
"""

import json
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

from config import settings


_client: chromadb.ClientAPI | None = None
_collection: chromadb.Collection | None = None


def _get_collection() -> chromadb.Collection:
    global _client, _collection
    if _collection is not None:
        return _collection

    _client = chromadb.PersistentClient(path=settings.chroma_db_path)

    embedding_fn = OpenAIEmbeddingFunction(
        api_key=settings.openai_api_key,
        model_name=settings.openai_embedding_model,
    )

    _collection = _client.get_or_create_collection(
        name="fraud_cases",
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )
    return _collection


def seed_fraud_cases(fraud_cases_dir: str = "data/fraud_cases"):
    """fraud_cases 디렉토리의 JSON 파일들을 ChromaDB에 시딩한다."""
    collection = _get_collection()
    cases_path = Path(fraud_cases_dir)

    if not cases_path.exists():
        print(f"Directory not found: {fraud_cases_dir}")
        return

    existing_ids = set(collection.get()["ids"])
    added = 0

    for json_file in sorted(cases_path.glob("*.json")):
        case = json.loads(json_file.read_text(encoding="utf-8"))
        case_id = case.get("case_id", json_file.stem)

        if case_id in existing_ids:
            continue

        # 임베딩용 텍스트 구성
        doc_text = _case_to_text(case)

        collection.add(
            ids=[case_id],
            documents=[doc_text],
            metadatas=[{
                "case_id": case_id,
                "fraud_type": case.get("fraud_type", ""),
                "country": case.get("country", "ID"),
                "outcome": case.get("outcome", ""),
                "date": case.get("date", ""),
            }],
        )
        added += 1

    print(f"Seeded {added} fraud cases (total: {collection.count()})")


def _case_to_text(case: dict) -> str:
    """사기 사례를 임베딩용 텍스트로 변환"""
    parts = [
        f"Fraud Type: {case.get('fraud_type', 'unknown')}",
        f"Description: {case.get('description', '')}",
        f"Indicators: {', '.join(case.get('indicators', []))}",
        f"Amount Range: {case.get('amount_range', 'N/A')}",
        f"Outcome: {case.get('outcome', 'N/A')}",
        f"Action Taken: {case.get('action_taken', 'N/A')}",
    ]
    return "\n".join(parts)


def search_similar_cases(
    transaction_description: str,
    top_k: int | None = None,
) -> list[dict]:
    """거래 정보를 바탕으로 유사 사기 사례를 검색한다."""
    collection = _get_collection()

    if collection.count() == 0:
        return []

    k = top_k or settings.rag_top_k

    results = collection.query(
        query_texts=[transaction_description],
        n_results=min(k, collection.count()),
    )

    cases = []
    if results and results["documents"]:
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0
            cases.append({
                "document": doc,
                "metadata": meta,
                "similarity_score": round(1 - distance, 4),
            })

    return cases


def format_similar_cases(cases: list[dict]) -> str:
    """검색된 유사 사례를 프롬프트용 텍스트로 변환"""
    if not cases:
        return "No similar fraud cases found in the knowledge base."

    lines = [f"Found {len(cases)} similar fraud case(s):"]
    for i, case in enumerate(cases, 1):
        meta = case.get("metadata", {})
        lines.append(f"\n--- Similar Case {i} (similarity: {case['similarity_score']}) ---")
        lines.append(f"Case ID: {meta.get('case_id', 'N/A')}")
        lines.append(f"Fraud Type: {meta.get('fraud_type', 'N/A')}")
        lines.append(case["document"])
    return "\n".join(lines)
