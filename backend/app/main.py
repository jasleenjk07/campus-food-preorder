from fastapi import FastAPI

app = FastAPI(title = "Campus Food Pre-Order API")

@app.get("/")
def root():
    return {"message: Backend is running"}

