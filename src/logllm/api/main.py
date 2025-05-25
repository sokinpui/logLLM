from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers
from .routers import normalize_ts_router  # ADDED
from .routers import (  # es_parse_router, # REMOVED
    analyze_errors_router,
    collect_router,
    container_router,
    dashboard_router,
    group_info_router,
    static_grok_parse_router,
)

app = FastAPI(
    title="LogLLM API",
    description="API for interacting with LogLLM functionalities.",
    version="0.1.0",
)

origins = [
    "http://localhost:5173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(dashboard_router.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(
    analyze_errors_router.router, prefix="/api/analyze-errors", tags=["Analyze Errors"]
)
app.include_router(collect_router.router, prefix="/api/collect", tags=["Collect"])
app.include_router(
    container_router.router, prefix="/api/container", tags=["Container Management"]
)
app.include_router(
    group_info_router.router, prefix="/api/groups", tags=["Group Information"]
)
app.include_router(
    static_grok_parse_router.router,
    prefix="/api/static-grok-parser",
    tags=["Static Grok Parser"],
)
app.include_router(
    normalize_ts_router.router,
    prefix="/api/normalize-ts",
    tags=["Timestamp Normalizer"],
)


@app.get("/api/health", tags=["Health"])
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "logllm.api.main:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
        reload=True,
    )
