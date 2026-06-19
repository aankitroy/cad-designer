from fastapi import FastAPI

app = FastAPI(title="cad-designer engine")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
