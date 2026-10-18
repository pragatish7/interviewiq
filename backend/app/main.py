"""
InterviewIQ - AI-Powered Mock Interview Performance Analyzer
Main FastAPI Application
"""
import os
import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database.database import init_db
from app.routes.interviews import router as interviews_router
from app.routes.dashboard import router as dashboard_router
from app.routes.live_interviews import router as live_interviews_router
from app.routes.coach import router as coach_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - initialize DB and ML model on startup."""
    logger.info("Starting InterviewIQ backend...")
    init_db()

    # Train ML model if not exists
    try:
        from app.ml.train import train_and_evaluate
        model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models", "model.pkl")
        if not os.path.exists(model_path):
            logger.info("No trained model found. Training on synthetic data...")
            train_and_evaluate()
        else:
            logger.info("ML model found.")
    except Exception as e:
        logger.warning(f"ML model initialization: {e}")

    yield
    logger.info("Shutting down InterviewIQ backend...")


app = FastAPI(
    title="InterviewIQ API",
    description="AI-Powered Mock Interview Performance Analyzer",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(interviews_router)
app.include_router(dashboard_router)
app.include_router(live_interviews_router)
app.include_router(coach_router)


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "app": "InterviewIQ", "version": "1.0.0"}


@app.get("/api/model/info")
async def model_info():
    from app.ml.predict import get_model_info
    return get_model_info()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
