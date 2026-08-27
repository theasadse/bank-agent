# AI-Powered Schedule of Charges (SOC) & Banking Assistant

> **100% Free, Local-First, Zero-API-Cost Stack** powered by IBM Docling, FastEmbed, ChromaDB, and Ollama (`llama3.2`) with instant Groq Cloud toggle.

---

## Architecture & Free Stack Layer

| Layer | Free Tool | Why It Fits |
|---|---|---|
| **PDF & Table Parser** | **Docling** (IBM Open Source) + pdfplumber | Runs locally on CPU/GPU; accurately parses multi-page complex tables into structured Markdown and extracts footnotes. |
| **Embeddings** | **FastEmbed** (`BAAI/bge-small-en-v1.5`) | Runs locally via ONNX runtime directly on CPU; fast, lightweight (~67MB), zero API key needed. |
| **Vector Database** | **ChromaDB** | Free, open-source embedded vector database saved directly to disk (`./data/chroma_db`). |
| **LLM Inference** | **Ollama** (`llama3.2`) / **Groq Free** | Ollama runs 100% locally offline; Groq / Gemini free tiers provide high-speed cloud inference at $0. |

---

## Core Capabilities (MVP & Production Features)

1. **Complex Fee Lookup**:
   - Queries debit card annual fees, replacement charges, ATM withdrawal limits, cheque book costs, and interbank fund transfer (IBFT) charges without forcing users to read 50-page PDFs.
2. **Table & Footnote Understanding**:
   - Correlates nested table rows with footnote markers (`*`, `**`, `1`, `2`, `†`, `#`, `Note:`, `Waiver Condition`) to explain threshold fee waivers and foreign conversion conditions.
3. **Card & Account Variant Comparison**:
   - Generates side-by-side comparative matrices (e.g. Classic vs Gold vs Platinum vs Infinite Debit Cards, or Current vs Savings vs Asaan vs BBA vs Premier Accounts).
4. **Tax & Surcharge Calculation (Plain Math Breakdown)**:
   - Calculates base fees alongside local statutory taxes (16% FED / Provincial Sales Tax / VAT, Withholding Tax under Sec 231A/236P/236Y, Filer vs Non-Filer rates).
5. **Source Attribution & Citations**:
   - Cites exact page numbers, section titles, and snippet context for compliance and auditability.
6. **SOC Document Vault**:
   - Ingest any custom Bank SOC PDF via drag-and-drop or use the pre-loaded 2025 Schedule of Charges.

---

## Quick Start Guide

### 1. Requirements & Prerequisites
- Python 3.10+
- Ollama installed with `llama3.2` model (`ollama run llama3.2`)

### 2. Run the Application
Start the backend server on `http://127.0.0.1:8000`:
```bash
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
```

Open your browser and navigate to:
```
http://127.0.0.1:8000
```

---

## Project Structure

```
bank-soc-AGENT/
├── backend/
│   ├── app.py                 # FastAPI web application & static server
│   ├── config.py              # Environment configuration & directory paths
│   ├── models.py              # Pydantic data models for queries & calculations
│   ├── parser.py              # Docling & pdfplumber table & footnote extractor
│   ├── vector_store.py        # FastEmbed + ChromaDB persistence layer
│   ├── llm_router.py          # Provider switcher (Groq ↔ Ollama ↔ Gemini)
│   ├── rag_engine.py          # Banking SOC RAG engine & prompt orchestrator
│   ├── calculator.py          # Tax, FED, VAT & surcharge calculation engine
│   └── sample_data/           # Pre-loaded Schedule of Charges PDF
├── frontend/
│   ├── index.html             # Luxury dark/glassmorphic interface
│   ├── style.css              # Bespoke modern CSS styling
│   └── app.js                 # Interactive logic, streaming SSE, calculator, comparator
├── data/
│   ├── chroma_db/             # Embedded ChromaDB vector storage
│   └── uploads/               # Uploaded custom bank PDFs
└── README.md
```
