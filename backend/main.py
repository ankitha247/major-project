import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.mongo import connect_db, close_db
from app.middleware.logging_middleware import LoggingMiddleware

from app.api.routes import auth, session, interview
from app.websocket.interview_ws import router as interview_ws_router
from app.websocket.emotion_ws import router as emotion_ws_router

from app.api.routes import auth, session, interview, report, evidence , emotion

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting ForensicAI backend...")
    await connect_db()
    yield
    logger.info("Shutting down ForensicAI backend...")
    await close_db()


app = FastAPI(
    title="ForensicAI",
    description="AI-powered crime witness interview platform",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(LoggingMiddleware)

API_PREFIX = "/api/v1"
app.include_router(auth.router,      prefix=API_PREFIX)
app.include_router(session.router,   prefix=API_PREFIX)
app.include_router(interview.router, prefix=API_PREFIX)
app.include_router(report.router, prefix=API_PREFIX)
# WebSockets — no prefix needed
app.include_router(interview_ws_router)
app.include_router(emotion_ws_router)
app.include_router(evidence.router, prefix=API_PREFIX)
app.include_router(emotion.router, prefix=API_PREFIX)

@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok", "version": app.version}