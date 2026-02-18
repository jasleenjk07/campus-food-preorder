#Connect Database to app
import logging #Python’s built-in logging module. Logging means: Recording what your application is doing while it is running.

import asyncio

import redis.asyncio as redis

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse #Custom error response
from fastapi.middleware.cors import CORSMiddleware

from starlette.exceptions import HTTPException as StarletteHTTPException #To catch ALL HTTP errors globally
from starlette.middleware.base import BaseHTTPMiddleware #BaseHTTPMiddleware allows you to intercept: Incoming request, Outgoing response. Before it reaches the client.

from app.database import engine, SessionLocal
from app import models
from app.routers import auth, users, admin, menu, orders, notifications, ws
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

if settings.ENVIRONMENT == "production":
    origins = ["https://cravix.com"]
else:
    origins = ["*"] #Allow all origins.

app.add_middleware(
    CORSMiddleware, #CORS = Cross-Origin Resource Sharing, It controls which frontend domains are allowed to call your backend API.
    allow_origins=origins, #Defines who can call your backend
    allow_credentials=True, #Allows cookies, authentication tokens, etc. to be sent with the request.
    allow_methods=["*"], #Allows all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"], #Allows all headers (Authorization, Content-Type, etc.)
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
    models.Base.metadata.create_all(bind=engine)
    asyncio.create_task(manager.start_listener())

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
        print("Redis error:", e)

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