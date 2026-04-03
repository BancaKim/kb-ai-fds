"""
KB Indonesia AI FDS PoC - FastAPI 엔트리포인트
"""

import logging
import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from api.routes import router
from db.database import init_db
from llm.rag import seed_fraud_cases

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

FDS_API_KEY = os.environ.get("FDS_API_KEY", "")
EXEMPT_PATHS = {"/", "/docs", "/openapi.json", "/redoc"}


# --- API Key 인증 미들웨어 ---
class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not FDS_API_KEY:
            return await call_next(request)  # dev mode
        if request.url.path in EXEMPT_PATHS or not request.url.path.startswith("/api"):
            return await call_next(request)
        key = request.headers.get("X-API-Key", "")
        if key != FDS_API_KEY:
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
        return await call_next(request)


# --- Rate Limiting 미들웨어 ---
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _clean_old(self, key: str, window: int):
        cutoff = time.time() - window
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api"):
            return await call_next(request)
        ip = request.client.host if request.client else "unknown"
        is_eval = request.url.path.startswith("/api/transactions")
        limit, window = (100, 60) if is_eval else (10, 60)
        bucket = f"{ip}:{'eval' if is_eval else 'mgmt'}"
        self._clean_old(bucket, window)
        if len(self._requests[bucket]) >= limit:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
        self._requests[bucket].append(time.time())
        return await call_next(request)


# --- 요청 로깅 미들웨어 ---
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration = (time.time() - start) * 1000
        ip = request.client.host if request.client else "-"
        logging.getLogger("access").info(
            f"{request.method} {request.url.path} {ip} {response.status_code} {duration:.0f}ms"
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logging.info("Initializing KB Indonesia AI FDS...")
    init_db()
    try:
        seed_fraud_cases()
    except Exception as e:
        logging.warning(f"Knowledge base seeding skipped: {e}")
    logging.info("FDS ready.")
    yield
    # Shutdown
    logging.info("FDS shutting down.")


app = FastAPI(
    title="KB Indonesia AI FDS",
    description="LLM-based Fraud Detection System PoC for KB Indonesia",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 설정 (환경변수 지원)
cors_origins = os.environ.get("FDS_CORS_ORIGINS", "http://localhost:8501,http://127.0.0.1:8501")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in cors_origins.split(",")],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-API-Role", "X-API-Operator"],
    allow_credentials=True,
)

# 보안 미들웨어 (순서 중요: 로깅 → 인증 → Rate Limit)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(APIKeyAuthMiddleware)
app.add_middleware(RateLimitMiddleware)

if not FDS_API_KEY:
    logging.warning("⚠ FDS_API_KEY not set — API authentication disabled (dev mode)")

app.include_router(router)


@app.get("/")
def root():
    return {"service": "KB Indonesia AI FDS", "version": "0.1.0", "status": "running"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
