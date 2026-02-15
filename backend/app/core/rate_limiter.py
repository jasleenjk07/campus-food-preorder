#Redis-backed rate limiter for the entire FastAPI app. Instead of storing rate limit counters in memory (which breaks when scaling), storing them in Redis (shared, centralized).
from slowapi import Limiter #It: Tracks how many requests a user makes, Blocks them if they exceed the limit
from slowapi.util import get_remote_address #Gets user IP address

limiter = Limiter(key_func=get_remote_address)