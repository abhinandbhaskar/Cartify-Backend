from fastapi import FastAPI

app = FastAPI(
    title="Cartify API",
    description="E-commerce REST API built with FastAPI",
    version="1.0.0"
)
@app.get("/")
def greet():
    return {"message":"Welcome to Cartify API"}
