import logging
import os
import asyncio
import redis.asyncio as redis

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from starlette.exceptions import HTTPException as StarletteHTTPException #To catch ALL HTTP errors globally
from starlette.middleware.base import BaseHTTPMiddleware #BaseHTTPMiddleware allows you to intercept: Incoming request, Outgoing response. Before it reaches the client.

from app.database import engine, SessionLocal
from app import models

from app.routers import auth
from app.routers import users
from app.routers import admin
from app.routers import menu
from app.routers import orders
from app.routers import notifications
from app.routers import ws
from app.routers import cart
from app.routers.pickup import router as pickup_router
from app.routers import vendor_dashboard
from app.routers import vendor_profile
from app.routers import home

from app.config import settings
from app.core.rate_limiter import limiter #Main rate limit engine
from app.core.redis_ws import manager

from slowapi.util import get_remote_address #Gets user IP address
from slowapi.errors import RateLimitExceeded #Exception when limit crossed
from slowapi.middleware import SlowAPIMiddleware #Middleware to activate limiter

from sqlalchemy import text

from pythonjsonlogger import jsonlogger

app = FastAPI(title="Cravix API") #Creates FastAPI application object
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# CORS: Android native apps do not need this; useful for web / admin panels.
_raw_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
if _raw_origins == ["*"]:
    origins = ["*"]
    allow_credentials = False  # browsers reject credentials + wildcard
else:
    origins = _raw_origins
    allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SecurityHeadersMiddleware(BaseHTTPMiddleware): #Middleware = a layer that runs before and/or after every request.
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff" #Prevents MIME-type sniffing.
        response.headers["X-Frame-Options"] = "DENY" #Prevents clickjacking attacks.
        response.headers["X-XSS-Protection"] = "1; mode=block" #Prevents XSS attacks.
        return response

app.add_middleware(SecurityHeadersMiddleware)

logHandler = logging.StreamHandler() #StreamHandler = writes logs to a stream (console, file, etc.)
formatter = jsonlogger.JsonFormatter( #Convert all logs into structured JSON with these fields.
    '%(asctime)s %(levelname)s %(name)s %(message)s'
)
logHandler.setFormatter(formatter)

rootLogger = logging.getLogger()
rootLogger.setLevel(settings.LOG_LEVEL)
rootLogger.addHandler(logHandler) #Add the handler to the root logger.

logger = logging.getLogger(__name__) #__name__ means the file name.

API_V1_PREFIX = "/api/v1" #base path for all version 1 APIs

app.include_router(auth.router, prefix=f"{API_V1_PREFIX}/auth")
app.include_router(users.router, prefix=f"{API_V1_PREFIX}/users")
app.include_router(admin.router, prefix=f"{API_V1_PREFIX}/admin")
app.include_router(menu.router, prefix=f"{API_V1_PREFIX}/menu")
app.include_router(orders.router, prefix=f"{API_V1_PREFIX}/orders") #Registers all order routes with your FastAPI app.
app.include_router(notifications.router, prefix=f"{API_V1_PREFIX}/notifications")
app.include_router(ws.router, prefix=f"{API_V1_PREFIX}", tags=["WebSocket"])
app.include_router(cart.router, prefix=f"{API_V1_PREFIX}/cart")
app.include_router(pickup_router, prefix=f"{API_V1_PREFIX}/pickup")
app.include_router(vendor_dashboard.router, prefix=f"{API_V1_PREFIX}/vendor")
app.include_router(vendor_profile.router, prefix=f"{API_V1_PREFIX}/vendor")
app.include_router(home.router, prefix=f"{API_V1_PREFIX}/home")

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

#A simple test API 
@app.get("/")
def root():
    return {"message": "Backend is running"}

@app.exception_handler(StarletteHTTPException) #Created a global error handler for all HTTPExceptions in FastAPI. Whenever any HTTPException happens anywhere in the app, run this function. Errors you raise manually (404, 403, etc.)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "type": "HTTP_Error",
                "message": exc.detail
            }
        }
    )

@app.exception_handler(Exception) #It catches ANY unexpected error in your entire application that is not an HTTPException. Unexpected crashes (bugs, DB errors, NoneType errors, etc.)
async def global_exception_handler(request: Request, exc: Exception):
    # Log full error internally
    logger.error(f"Unhandled error: {str(exc)}", exc_info=True)

    if settings.ENVIRONMENT == "development":
        return JSONResponse(
            status_code=500, #Server crashed due to unexpected error
            content={
                "success": False,
                "error": {
                    "type": "INTERNAL_SERVER_ERROR",
                    "message": str(exc)
                }
            },
        )

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "type": "INTERNAL_SERVER_ERROR",
                "message": "Something went wrong"
            }
        },
    )

@app.exception_handler(RateLimitExceeded) #request control protection
async def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429, #Status code 429 = Too Many Requests
        content={
            "success": False,
            "error": {
                "type": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests. Please slow down."
            }
        }
    )

@app.on_event("startup")
async def startup_event():
    try:
        models.Base.metadata.create_all(bind=engine)
    except Exception as exc:
        logger.error("Database init failed on startup: %s", exc)
    try:
        asyncio.create_task(manager.start_listener())
    except Exception as exc:
        logger.error("Redis websocket listener failed on startup: %s", exc)

#Health check endpoint: It just confirms app is alive, the server is running, and Redis is connected. App process alive
@app.get("/health/live") 
async def liveness_check():
    return {
        "status": "alive"
    }

#This is a Readiness Probe. App + Database working
@app.get("/health/ready")
async def readiness_check():
    db_status = "disconnected"
    redis_status = "disconnected"

    #Check DB
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "connected"
    except Exception:
        pass

    #Check Redis
    try:
        r = redis.from_url(settings.REDIS_URL)
        await r.ping()
        redis_status = "connected"
    except Exception as e:
        logger.warning("Redis readiness check failed: %s", e)

    status = "ready" if db_status == "connected" and redis_status == "connected" else "not_ready"
    
    return {
        "status": status,
        "database": db_status,
        "redis": redis_status
    }

@app.get("/health")
async def full_health():
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT
    }