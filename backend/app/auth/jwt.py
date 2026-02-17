from datetime import datetime, timedelta
from jose import jwt #Creates JWT tokens
from app.config import settings

SECRET_KEY = settings.SECRET_KEY 
ALGORITHM = settings.ALGORITHM 
ACCESS_TOKEN_EXPIRE_MINUTES = 60 #Token validity duration

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire}) #JWT has a standard claim called exp

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt