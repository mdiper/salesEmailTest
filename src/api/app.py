from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routing_rules import router as routing_router
from src.api.emails import router as emails_router
from src.api.stats import router as stats_router
from src.api.auth import router as auth_router
from src.api.forwarding import router as forwarding_router

app = FastAPI(
    title="SalesEmailTool API",
    version="1.0.0",
    description="API per gestione email, analisi di sicurezza e routing automatico",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(emails_router)
app.include_router(stats_router)
app.include_router(routing_router)
app.include_router(forwarding_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
