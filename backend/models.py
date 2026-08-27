from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class Citation(BaseModel):
    document_name: str
    page_number: int
    section_title: str
    snippet: str
    score: Optional[float] = None

class ChatMessage(BaseModel):
    role: str # 'user', 'assistant', 'system'
    content: str

class ChatRequest(BaseModel):
    query: str
    history: Optional[List[ChatMessage]] = Field(default_factory=list)
    provider: Optional[str] = "auto" # 'auto', 'groq', 'ollama', 'gemini'
    model_name: Optional[str] = None
    api_key: Optional[str] = None # Optional user-supplied key from UI
    filter_document: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str
    citations: List[Citation] = Field(default_factory=list)
    provider_used: str
    model_used: str
    has_footnotes_referenced: bool = False
    footnotes_detail: Optional[List[str]] = None

class CompareRequest(BaseModel):
    category: str # e.g. "debit_cards", "credit_cards", "accounts", "lockers"
    items: List[str] # e.g. ["Classic Debit Card", "Gold Debit Card", "Platinum Debit Card", "Infinite Debit Card"]
    provider: Optional[str] = "auto"
    model_name: Optional[str] = None
    api_key: Optional[str] = None

class ComparisonFeature(BaseModel):
    feature_name: str
    values: Dict[str, str] # item_name -> fee or detail

class CompareResponse(BaseModel):
    title: str
    items: List[str]
    matrix: List[ComparisonFeature]
    footnotes_and_waivers: List[str] = Field(default_factory=list)
    recommendation: Optional[str] = None
    citations: List[Citation] = Field(default_factory=list)

class TaxCalculateRequest(BaseModel):
    base_fee: float
    service_name: Optional[str] = "Banking Service"
    fed_rate: Optional[float] = 16.0 # FED/VAT percentage
    is_filer: Optional[bool] = True
    wht_rate: Optional[float] = 0.0 # Withholding Tax percentage
    transaction_amount: Optional[float] = 0.0
    intl_markup_rate: Optional[float] = 0.0

class TaxCalculateResponse(BaseModel):
    service_name: str
    base_fee: float
    fed_amount: float
    wht_amount: float
    intl_markup_amount: float
    total_fee_charged: float
    breakdown_steps: List[str]
    footnote_rule_applied: Optional[str] = None

class IngestionStatus(BaseModel):
    document_name: str
    total_pages: int
    total_chunks: int
    tables_extracted: int
    footnotes_found: int
    status: str
    message: Optional[str] = None

class SystemHealth(BaseModel):
    ollama_online: bool
    ollama_models: List[str]
    groq_configured: bool
    gemini_configured: bool
    indexed_documents: int
    total_chunks: int
    embedding_model: str
