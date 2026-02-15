import redis #Python client to connect to your Redis server.
import json

redis_client = redis.Redis(host="localhost", port=6379, db=1) #Connect to Redis running on: Host: localhost, Port: 6379, Database: 1

CACHE_TTL = 300 #5 minutes: how long cached data lives. After 5 minutes: Redis automatically deletes the cached value.

#Retrieve the value from Redis.
def get_cache(key: str):
    data = redis_client.get(key)
    if data:
        return json.loads(data)
    return None

#Store the value in Redis with a TTL.
def set_cache(key: str, value):
    redis_client.setex( #setex = set with expiration (Set value + Expiry time)
        key,
        CACHE_TTL,
        json.dumps(value)
    )

#Delete the value from Redis.
def delete_cache(key: str):
    redis_client.delete(key)