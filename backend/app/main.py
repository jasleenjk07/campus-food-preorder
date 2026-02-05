#Connect Database to app
from fastapi import FastAPI
from app.database import engine
from app import models

app = FastAPI(title = "Campus Food Pre-Order API") #Creates FastAPI application object

#Create database tables
models.Base.metadata.create_all(bind=engine)

@app.get("/")
def root():
    return {"message: Backend is running"}

