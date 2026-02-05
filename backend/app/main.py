#Connect Database to app
print(">>> RUNNING backend/app/main.py <<<")
from fastapi import FastAPI
from app.database import engine
from app import models
from app.routers import auth

app = FastAPI(title="Campus Food Pre-Order API") #Creates FastAPI application object

#Create database tables
models.Base.metadata.create_all(bind=engine)

app.include_router(auth.router)

#A simple test API 
@app.get("/")
def root():
    return {"message": "Backend is running"}
