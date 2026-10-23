from fastapi import FastAPI

app = FastAPI(title="IvoStock Ingesta")

@app.get("/")
def read_root():
    return {"status": "ok", "service": "ingesta"}
