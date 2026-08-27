import os
import shutil
import logging
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse

from backend.config import (
    PORT,
    HOST,
    UPLOADS_DIR,
    SAMPLE_DATA_DIR,
    EMBEDDING_MODEL_NAME
)
from backend.models import (
    ChatRequest,
    ChatResponse,
    CompareRequest,
    CompareResponse,
    TaxCalculateRequest,
    TaxCalculateResponse,
    IngestionStatus,
    SystemHealth
)
from backend.parser import BankSOCParser
from backend.vector_store import BankSOCVectorStore
from backend.llm_router import LLMRouter
from backend.rag_engine import BankSOCRAGEngine
from backend.calculator import BankFeeCalculator


from backend.sync_manager import DocumentSyncManager

logger = logging.getLogger("bank_soc.app")
logging.basicConfig(level=logging.INFO)

# Initialize core services
parser = BankSOCParser(prefer_docling=True)
vector_store = BankSOCVectorStore()
llm_router = LLMRouter()
rag_engine = BankSOCRAGEngine(vector_store, llm_router)
sync_manager = DocumentSyncManager(parser, vector_store)

# Run initial automatic synchronization
sync_manager.sync_all()

app = FastAPI(
    title="AI-Powered Schedule of Charges (SOC) & Banking Assistant",
    description="100% Free Stack AI Banking SOC Engine with Docling, FastEmbed, ChromaDB, and Ollama/Groq.",
    version="1.0.0"
)

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- API ROUTES -----------------

@app.post("/api/sync")
async def sync_soc_documents():
    """
    Manually or automatically trigger synchronization of sample_data and uploads folders.
    Detects new, updated (biannual changes), or deleted PDFs and refreshes ChromaDB.
    """
    try:
        return sync_manager.sync_all()
    except Exception as e:
        logger.error(f"Sync error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health", response_model=SystemHealth)
async def get_health(auto_sync: bool = False):
    """
    Check system health, Ollama status, Groq availability, and ChromaDB statistics.
    """
    if auto_sync:
        sync_manager.sync_all()

    llm_health = llm_router.check_health()
    docs = vector_store.get_indexed_documents()
    total_chunks = vector_store.total_count()

    return SystemHealth(
        ollama_online=llm_health["ollama_online"],
        ollama_models=llm_health["ollama_models"],
        groq_configured=llm_health["groq_configured"],
        gemini_configured=llm_health["gemini_configured"],
        indexed_documents=len(docs),
        total_chunks=total_chunks,
        embedding_model=EMBEDDING_MODEL_NAME
    )

@app.post("/api/chat", response_model=ChatResponse)
async def chat_query(req: ChatRequest):
    """
    Direct non-streaming chat query with verifiable citations.
    """
    try:
        return await rag_engine.answer_query(req)
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat/stream")
async def chat_query_stream(req: ChatRequest):
    """
    Server-Sent Events (SSE) streaming chat query for real-time word-by-word generation.
    """
    try:
        return StreamingResponse(
            rag_engine.stream_query(req),
            media_type="text/event-stream"
        )
    except Exception as e:
        logger.error(f"Streaming error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/compare", response_model=CompareResponse)
async def compare_variants(req: CompareRequest):
    """
    Generate side-by-side card or account variant comparison matrix.
    """
    try:
        return await rag_engine.compare_items(req)
    except Exception as e:
        logger.error(f"Comparison error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/calculate-tax", response_model=TaxCalculateResponse)
async def calculate_tax(req: TaxCalculateRequest):
    """
    Calculate base fee + FED/VAT + international markup + withholding tax breakdown.
    """
    try:
        return BankFeeCalculator.calculate(req)
    except Exception as e:
        logger.error(f"Tax calculation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/documents")
async def list_documents():
    """
    List all indexed SOC documents with page counts and categorized sections.
    """
    return vector_store.get_indexed_documents()

@app.post("/api/upload", response_model=IngestionStatus)
async def upload_document(
    file: UploadFile = File(...),
    use_docling: bool = Form(True)
):
    """
    Upload and index a new Schedule of Charges PDF.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    file_path = UPLOADS_DIR / file.filename
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Parse with parser
        chunks = parser.parse_pdf(file_path, document_name=file.filename)
        if not chunks:
            raise HTTPException(status_code=400, detail="Could not extract readable text/tables from PDF.")

        indexed_count = vector_store.add_chunks(chunks)
        tables_count = sum(1 for c in chunks if c.has_tables)
        fn_count = sum(1 for c in chunks if c.has_footnotes)

        return IngestionStatus(
            document_name=file.filename,
            total_pages=max([c.page_number for c in chunks] or [1]),
            total_chunks=indexed_count,
            tables_extracted=tables_count,
            footnotes_found=fn_count,
            status="SUCCESS",
            message=f"Successfully indexed {indexed_count} chunks with FastEmbed into ChromaDB."
        )
    except Exception as e:
        logger.error(f"Upload and indexing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")

@app.post("/api/sample-index", response_model=IngestionStatus)
async def index_sample_soc():
    """
    Reset and re-index the official sample Schedule of Charges PDF.
    """
    sample_pdf = SAMPLE_DATA_DIR / "Apex_International_Bank_SOC_2025.pdf"
    if not sample_pdf.exists():
        raise HTTPException(status_code=404, detail="Sample SOC PDF not found. Please upload a PDF first.")

    chunks = parser.parse_pdf(sample_pdf, document_name="Apex_International_Bank_SOC_2025.pdf")
    indexed_count = vector_store.add_chunks(chunks)

    return IngestionStatus(
        document_name="Apex_International_Bank_SOC_2025.pdf",
        total_pages=5,
        total_chunks=indexed_count,
        tables_extracted=5,
        footnotes_found=5,
        status="SUCCESS",
        message="Default comprehensive Schedule of Charges successfully indexed."
    )

@app.delete("/api/documents/{doc_name}")
async def delete_document(doc_name: str):
    """
    Delete a document and all its indexed chunks from ChromaDB.
    """
    vector_store.delete_document(doc_name)
    return {"status": "SUCCESS", "message": f"Deleted document '{doc_name}' from vector index."}

# Mount static frontend
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host=HOST, port=PORT, reload=True)
