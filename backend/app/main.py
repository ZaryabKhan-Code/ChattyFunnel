from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.config import settings
from app.database import init_db
from app.routers import (
    auth,
    accounts,
    messages,
    webhooks,
    users,
    debug,
    websocket,
    ai,
    media,
    workspaces,
    funnels,
    ai_bots,
    attachments,
)
from app.routers.attachments import get_upload_dir

# Initialize FastAPI app
app = FastAPI(
    title="Social Messaging Integration API",
    description="API for connecting Facebook and Instagram accounts and managing messages",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users.router, prefix=f"{settings.API_V1_STR}")
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}")
app.include_router(accounts.router, prefix=f"{settings.API_V1_STR}")
app.include_router(messages.router, prefix=f"{settings.API_V1_STR}")
app.include_router(webhooks.router, prefix=f"{settings.API_V1_STR}")
app.include_router(debug.router, prefix=f"{settings.API_V1_STR}")
app.include_router(websocket.router, prefix=f"{settings.API_V1_STR}")
app.include_router(ai.router, prefix=f"{settings.API_V1_STR}")
app.include_router(media.router, prefix=f"{settings.API_V1_STR}")

# New workspace system routers
app.include_router(workspaces.router, prefix=f"{settings.API_V1_STR}")
app.include_router(funnels.router, prefix=f"{settings.API_V1_STR}")
app.include_router(ai_bots.router, prefix=f"{settings.API_V1_STR}")
app.include_router(attachments.router, prefix=f"{settings.API_V1_STR}")

# Mount static files for attachments
uploads_dir = get_upload_dir()
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_db()


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Social Messaging Integration API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
