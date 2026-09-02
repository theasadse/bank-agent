import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger("bank_soc.parser")
logging.basicConfig(level=logging.INFO)

@dataclass
class ParsedChunk:
    text: str
    document_name: str
    page_number: int
    section_title: str
    category: str
    has_tables: bool = False
    has_footnotes: bool = False
    raw_footnotes: Optional[List[str]] = None

class BankSOCParser:
    """
    Advanced Schedule of Charges (SOC) PDF & Table Parser.
    Uses Docling for neural document & table structure parsing,
    with an intelligent pdfplumber fallback for rapid multi-page table & footnote extraction.
    """

    FOOTNOTE_PATTERNS = [
        r"^\s*(\*+|\†|\#|\d+[\.\)]|\[\d+\])\s+(.+)$",
        r"^\s*(Note\s*\d*|Important\s*Note|Waiver\s*Condition|FED\s*Rule|Tax\s*Note)[:\-]\s*(.+)$",
    ]

    CATEGORY_KEYWORDS = {
        "debit_cards": ["debit card", "paypak", "visa debit", "mastercard debit", "unionpay", "card annual fee", "card replacement", "pin generation", "chip card"],
        "credit_cards": ["credit card", "platinum card", "gold card", "classic card", "infinite", "cash advance", "finance charge", "late payment fee", "overlimit"],
        "accounts": ["current account", "savings account", "asaan account", "basic banking", "minimum balance", "account maintenance", "dormant account", "closing of account"],
        "fund_transfers": ["ibft", "interbank", "fund transfer", "raast", "rtgs", "clearing", "1link", "atm withdrawal", "same day clearing"],
        "cheque_books": ["cheque book", "pay order", "demand draft", "stop payment", "cdr", "manager cheque", "leaf"],
        "lockers": ["locker", "safe deposit", "small locker", "medium locker", "large locker", "key deposit", "locker breaking"],
        "remittance": ["foreign exchange", "inward remittance", "outward remittance", "swift", "fcy", "telex charge", "fcva", "cross border"],
        "taxes": ["fed", "federal excise duty", "sales tax", "withholding tax", "wht", "filer", "non-filer", "fbr", "statutory charges"]
    }

    def __init__(self, prefer_docling: bool = True):
        self.prefer_docling = prefer_docling
        self._docling_available = False
        try:
            from docling.document_converter import DocumentConverter
            self._docling_converter = DocumentConverter()
            self._docling_available = True
            logger.info("Docling DocumentConverter initialized successfully.")
        except Exception as e:
            logger.warning(f"Docling not available or failed to init: {e}. Using high-precision pdfplumber parser.")

    def parse_pdf(self, file_path: str | Path, document_name: Optional[str] = None) -> List[ParsedChunk]:
        """
        Main entrypoint: parses SOC PDF and returns chunked markdown with table structure and correlated footnotes.
        """
        file_path = Path(file_path)
        doc_name = document_name or file_path.name

        chunks = []
        # Attempt docling first if configured & available
        if self.prefer_docling and self._docling_available:
            try:
                logger.info(f"Parsing '{doc_name}' with IBM Docling...")
                chunks = self._parse_with_docling(file_path, doc_name)
                if chunks:
                    logger.info(f"Docling parsing succeeded with {len(chunks)} chunks.")
                    return chunks
            except Exception as e:
                logger.error(f"Docling parsing encountered error: {e}. Falling back to structured pdfplumber parser.")

        # Fallback / Fast parser
        logger.info(f"Parsing '{doc_name}' with high-precision table & footnote parser...")
        return self._parse_with_pdfplumber(file_path, doc_name)

    def _parse_with_docling(self, file_path: Path, doc_name: str) -> List[ParsedChunk]:
        conv_res = self._docling_converter.convert(file_path)
        doc = conv_res.document
        
        # Export full markdown
        markdown_text = doc.export_to_markdown()
        
        # Chunk by section / headers while preserving tables
        sections = re.split(r'\n(?=#{1,3}\s+)', markdown_text)
        chunks = []

        for idx, sec in enumerate(sections):
            sec_text = sec.strip()
            if not sec_text:
                continue
            
            # Extract section title
            first_line = sec_text.splitlines()[0]
            section_title = re.sub(r'^#+\s*', '', first_line).strip() if first_line.startswith('#') else f"Section {idx+1}"
            
            # Detect footnotes and categories
            category = self._infer_category(sec_text)
            has_tables = "|" in sec_text and "---" in sec_text
            footnotes = self._extract_footnotes(sec_text)

            enriched_text = f"[Document: {doc_name} | Section: {section_title} | Category: {category.replace('_', ' ').title()} | Page: {max(1, (idx // 2) + 1)}]\n{sec_text}"
            chunk = ParsedChunk(
                text=enriched_text,
                document_name=doc_name,
                page_number=max(1, (idx // 2) + 1),
                section_title=section_title,
                category=category,
                has_tables=has_tables,
                has_footnotes=len(footnotes) > 0,
                raw_footnotes=footnotes
            )
            chunks.append(chunk)

        return chunks

    def _parse_with_pdfplumber(self, file_path: Path, doc_name: str) -> List[ParsedChunk]:
        import pdfplumber

        chunks = []
        with pdfplumber.open(file_path) as pdf:
            current_section = "General Banking Information"

            for page_idx, page in enumerate(pdf.pages):
                page_num = page_idx + 1
                text = page.extract_text() or ""
                tables = page.extract_tables()

                # Separate body text vs footnotes at bottom
                body_lines, page_footnotes = self._split_body_and_footnotes(text)
                
                # Check for section header updates
                for line in body_lines[:4]:
                    clean_line = line.strip()
                    if re.match(r'^(Section|\d+\.|\bSECTION\b|[A-Z\s]{4,30}$)', clean_line) and len(clean_line) < 60:
                        current_section = clean_line
                        break

                # Format extracted tables into rich Markdown
                formatted_tables = []
                for table in tables:
                    md_table = self._table_to_markdown(table, page_footnotes)
                    if md_table:
                        formatted_tables.append(md_table)

                # Assemble page content
                page_content_parts = []
                page_content_parts.append(f"### {current_section} (Page {page_num})\n")

                if formatted_tables:
                    page_content_parts.append("\n\n".join(formatted_tables))
                else:
                    page_content_parts.append("\n".join(body_lines))

                # Append explicit correlated footnotes section if any exist
                if page_footnotes:
                    page_content_parts.append("\n\n**Applicable Footnotes & Waivers for this Section:**")
                    for fn in page_footnotes:
                        page_content_parts.append(f"- {fn}")

                raw_page_text = "\n".join(page_content_parts).strip()
                category = self._infer_category(raw_page_text)
                enriched_page_text = f"[Document: {doc_name} | Section: {current_section} | Category: {category.replace('_', ' ').title()} | Page: {page_num}]\n{raw_page_text}"

                chunk = ParsedChunk(
                    text=enriched_page_text,
                    document_name=doc_name,
                    page_number=page_num,
                    section_title=current_section,
                    category=category,
                    has_tables=len(tables) > 0,
                    has_footnotes=len(page_footnotes) > 0,
                    raw_footnotes=page_footnotes
                )
                chunks.append(chunk)

        return chunks

    def _split_body_and_footnotes(self, text: str) -> Tuple[List[str], List[str]]:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        body_lines = []
        footnotes = []
        in_footnote_section = False

        for line in lines:
            # Check if this line triggers footnote section
            is_fn = False
            for pat in self.FOOTNOTE_PATTERNS:
                if re.search(pat, line, re.IGNORECASE):
                    is_fn = True
                    break
            
            if is_fn or "Footnote" in line or "Important Notes:" in line:
                in_footnote_section = True
                footnotes.append(line)
            elif in_footnote_section:
                # Continuation of multi-line footnote
                footnotes.append(line)
            else:
                body_lines.append(line)

        return body_lines, footnotes

    def _table_to_markdown(self, table: List[List[Optional[str]]], footnotes: List[str]) -> str:
        if not table or len(table) < 1:
            return ""

        # Filter empty rows
        cleaned_table = []
        for row in table:
            if not row:
                continue
            cleaned_row = [str(cell).replace("\n", " ").strip() if cell is not None else "" for cell in row]
            if any(cleaned_row):
                cleaned_table.append(cleaned_row)

        if not cleaned_table:
            return ""

        # Normalize column counts
        max_cols = max(len(row) for row in cleaned_table)
        padded_table = [row + [""] * (max_cols - len(row)) for row in cleaned_table]

        # First row as header
        header = padded_table[0]
        rows = padded_table[1:]

        md_lines = []
        md_lines.append("| " + " | ".join(header) + " |")
        md_lines.append("| " + " | ".join(["---"] * max_cols) + " |")

        for row in rows:
            md_lines.append("| " + " | ".join(row) + " |")

        return "\n".join(md_lines)

    def _extract_footnotes(self, text: str) -> List[str]:
        footnotes = []
        for line in text.splitlines():
            line_str = line.strip()
            for pat in self.FOOTNOTE_PATTERNS:
                if re.search(pat, line_str, re.IGNORECASE):
                    footnotes.append(line_str)
                    break
        return footnotes

    def _infer_category(self, text: str) -> str:
        text_lower = text.lower()
        scores = {}
        for cat, keywords in self.CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[cat] = score

        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]
        return "general_banking"
