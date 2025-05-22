from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers
from .routers import (  # file_parse_router, # Placeholder for if you add one; es_parse_router,; normalize_ts_router,; pm_router,
    analyze_errors_router,
    collect_router,
    container_router,
    dashboard_router,
)

app = FastAPI(
    title="LogLLM API",
    description="API for interacting with LogLLM functionalities.",
    version="0.1.0",
)

# CORS (Cross-Origin Resource Sharing)
# Adjust origins as needed for production
origins = [
    "http://localhost:5173",  # Default Vite dev server
    "http://localhost:3000",  # Common React dev server
    # Add your frontend production URL when deployed
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
# app.include_router(es_parse_router.router, prefix="/api/es-parser", tags=["ES Parser"])
# app.include_router(file_parse_router.router, prefix="/api/file-parser", tags=["File Parser"])
# app.include_router(
#     normalize_ts_router.router,
#     prefix="/api/normalize-ts",
#     tags=["Normalize Timestamps"],
# )
# app.include_router(
#     pm_router.router, prefix="/api/prompts-manager", tags=["Prompts Manager"]
# )


@app.get("/api/health", tags=["Health"])
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    # Configuration for Uvicorn
    # You can adjust host, port, log_level, and reload as needed.
    # 'reload=True' is great for development, as it automatically restarts
    # the server when you save changes to your Python files.
    # For production, you'd typically set reload=False and use a process manager
    # like Gunicorn with Uvicorn workers.
    # The app path should be 'main:app' relative to the directory
    # from which uvicorn is being effectively run by this script.
    # Since we are in main.py and app is defined in this file, 'main:app'
    # or simply passing the app object directly works.
    uvicorn.run(
        "logllm.api.main:app",  # Path to the FastAPI app instance
        host="127.0.0.1",
        port=8000,
        log_level="info",
        reload=True,  # Set to False for production
    )
