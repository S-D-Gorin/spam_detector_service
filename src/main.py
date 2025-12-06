from fastapi import FastAPI
from .api import router as api_router  # если у тебя есть api.py

app = FastAPI(
    title="Spam Detector Service",
    version="0.1.0",
)

app.include_router(api_router, prefix="/api")

@app.get("/health")
def health():
    return {"status": "ok"}

# для локального запуска через `python -m src.main`
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
