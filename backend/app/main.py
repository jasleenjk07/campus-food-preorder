#Connect Database to app
from fastapi import FastAPI
from app.database import engine
from app import models
from app.routers import auth, users, admin, menu, orders

app = FastAPI(title="Campus Food Pre-Order API") #Creates FastAPI application object

#Create database tables
models.Base.metadata.create_all(bind=engine)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(admin.router)
app.include_router(menu.router)
app.include_router(orders.router) #Registers all order routes with your FastAPI app.

#A simple test API 
@app.get("/")
def root():
    return {"message": "Backend is running"}
