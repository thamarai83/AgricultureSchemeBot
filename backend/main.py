
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.routes.chat import router as chat_router
from backend.routes.ingestion import router as ingestion_router
from backend.routes.scraping import router as scraping_router
from backend.routes.upload import router as upload_router
from services.embedding_service import get_embeddings
from services.vector_store import has_persisted_index, load_vector_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.embeddings = None
    app.state.vector_store = None
    if has_persisted_index():
        app.state.embeddings = get_embeddings()
        app.state.vector_store = load_vector_store(app.state.embeddings)
    yield


app = FastAPI(
    title="Uzhavan AI Farmer Assistant",
    description="Tamil Nadu Government Farmer Scheme Assistant",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(upload_router)
app.include_router(scraping_router)
app.include_router(ingestion_router)
app.include_router(chat_router)


@app.get("/")
def home():
    return {
        "message": "Welcome to Uzhavan AI Farmer Assistant",
        "status": "Running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "application": "Uzhavan RAG Assistant",
        "message": "Backend is working successfully"
    }
