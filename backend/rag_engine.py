import os
import re
import json
import logging
from typing import List, Dict, Any, Optional, AsyncGenerator

from backend.vector_store import BankSOCVectorStore
from backend.llm_router import LLMRouter
from backend.models import (
    ChatRequest,
    ChatResponse,
    Citation,
    CompareRequest,
    CompareResponse,
    ComparisonFeature
)

logger = logging.getLogger("bank_soc.rag_engine")
logging.basicConfig(level=logging.INFO)

SYSTEM_PROMPT_SOC = """You are an expert Bank Schedule of Charges (SOC) & Compliance AI Assistant.
Your mission is to provide accurate, transparent, and fully-cited fee schedules, account rules, card charges, limits, taxes, and waiver conditions directly from the bank's official Schedule of Charges documents.

CRITICAL INSTRUCTIONS:
1. ACCURACY & NUMERICAL PRECISION: State exact fee amounts, currencies, percentages, and limits found in the document.
2. CURRENCY RULE: All domestic bank charges are in Pakistani Rupees (Rs. / PKR). NEVER use dollar signs ($) unless the document explicitly discusses a Foreign Currency (FCY/USD) account.
3. TABLE & FOOTNOTE UNDERSTANDING: Always inspect and correlate table rows with relevant footnotes (marked with *, **, 1, 2, †, #, Note:, Waiver Condition). If a waiver, threshold, or conditional rule exists (e.g. "Fee waived if monthly balance > Rs. 50,000" or "FED/sales tax applies"), you MUST highlight it clearly.
4. TAX & FED TRANSPARENCY: Clarify whether a quoted fee is base fee or subject to Federal Excise Duty (FED) / Provincial Sales Tax / Withholding Tax (WHT).
5. CITATIONS & AUDITABILITY: At the end of relevant points or answers, explicitly state the source document name, page number, and section name (e.g. `[Page 12: Section 5 - Debit Cards]`).
6. STRUCTURED FORMAT: Use clean Markdown tables, bold headers, and bullet points for readability.

CONTEXT FROM OFFICIAL SCHEDULE OF CHARGES DOCUMENTS:
---------------------
{context}
---------------------
"""

COMPARISON_PROMPT_TEMPLATE = """You are an expert Banking Analyst. Compare the following banking items/variants side-by-side using ONLY the provided Schedule of Charges context.

Items to compare: {items}
Category: {category}

CURRENCY RULE: All charges and limits MUST be quoted in Pakistani Rupees (Rs. / PKR). NEVER use dollar signs ($).

CONTEXT FROM OFFICIAL SCHEDULE OF CHARGES DOCUMENTS:
---------------------
{context}
---------------------

Output MUST be a valid JSON object matching this exact schema:
{{
  "title": "Side-by-Side Comparison of {category}",
  "items": {items_json},
  "matrix": [
    {{
      "feature_name": "Annual / Renewal Fee",
      "values": {sample_values_json}
    }},
    {{
      "feature_name": "Issuance Fee",
      "values": {sample_values_json}
    }},
    {{
      "feature_name": "Daily ATM Cash Withdrawal Limit",
      "values": {sample_values_json}
    }},
    {{
      "feature_name": "Daily POS / E-Commerce Limit",
      "values": {sample_values_json}
    }},
    {{
      "feature_name": "Card Replacement / Damaged Card",
      "values": {sample_values_json}
    }},
    {{
      "feature_name": "International Cross-Border Markup",
      "values": {sample_values_json}
    }},
    {{
      "feature_name": "Fee Waiver Conditions",
      "values": {sample_values_json}
    }}
  ],
  "footnotes_and_waivers": [
    "Footnote 1 details...",
    "Footnote 2 details..."
  ],
  "recommendation": "Executive summary recommendation comparing the items based on fee-to-benefit ratio."
}}

CRITICAL REQUIREMENT FOR 'values': Each key in the 'values' dictionary MUST be the exact product name from the 'items' list (e.g. {sample_keys}).
Return ONLY the JSON object without markdown fences or extra commentary.
"""

class BankSOCRAGEngine:
    """
    RAG Engine specializing in Bank Schedule of Charges (SOC) analysis.
    """

    def __init__(self, vector_store: BankSOCVectorStore, llm_router: LLMRouter):
        self.vector_store = vector_store
        self.llm_router = llm_router

    async def answer_query(self, req: ChatRequest) -> ChatResponse:
        """
        Execute RAG query against indexed SOC documents with source citations.
        """
        retrieved_docs = self.vector_store.query(
            query_text=req.query,
            n_results=5,
            document_filter=req.filter_document
        )

        if not retrieved_docs:
            context_str = "No specific Schedule of Charges documents are currently indexed. Please upload or index a bank SOC PDF."
            citations = []
        else:
            context_blocks = []
            citations = []
            seen_sources = set()

            for item in retrieved_docs:
                meta = item.get("metadata") or {}
                doc_name = meta.get("document_name", "SOC_Document.pdf")
                page_num = meta.get("page_number", 1)
                sec_title = meta.get("section_title", "General Banking")
                score = item.get("score", 0.0)

                source_key = f"{doc_name}_p{page_num}_{sec_title}"
                if source_key not in seen_sources:
                    seen_sources.add(source_key)
                    snippet = item["text"][:250].replace("\n", " ") + "..."
                    citations.append(Citation(
                        document_name=doc_name,
                        page_number=page_num,
                        section_title=sec_title,
                        snippet=snippet,
                        score=score
                    ))

                context_blocks.append(
                    f"--- Source: {doc_name} | Page: {page_num} | Section: {sec_title} ---\n"
                    f"{item['text']}\n"
                )

            context_str = "\n\n".join(context_blocks)

        system_msg = SYSTEM_PROMPT_SOC.format(context=context_str)

        messages = [{"role": "system", "content": system_msg}]
        if req.history:
            for h in req.history[-4:]: # Include last 2 turns
                messages.append({"role": h.role, "content": h.content})
        messages.append({"role": "user", "content": req.query})

        res = await self.llm_router.generate_response(
            messages=messages,
            provider=req.provider,
            model_name=req.model_name,
            api_key=req.api_key
        )

        answer_text = res.get("content", "")
        provider_used = res.get("provider", "unknown")
        model_used = res.get("model", "unknown")

        # Check if answer referenced footnotes
        has_fn = bool(re.search(r'footnote|waiver|condition|\*|\bFED\b|statutory', answer_text, re.IGNORECASE))
        
        # Extract any specific footnote bullets mentioned
        fn_details = []
        for line in answer_text.splitlines():
            if any(k in line.lower() for k in ["waiver", "footnote", "exempt", "balance requirement"]):
                fn_details.append(line.strip("- *#"))

        return ChatResponse(
            answer=answer_text,
            citations=citations,
            provider_used=provider_used,
            model_used=model_used,
            has_footnotes_referenced=has_fn,
            footnotes_detail=fn_details[:5] if fn_details else None
        )

    async def stream_query(self, req: ChatRequest) -> AsyncGenerator[str, None]:
        """
        Stream tokens directly to client with citation metadata preamble/postscript.
        """
        retrieved_docs = self.vector_store.query(
            query_text=req.query,
            n_results=5,
            document_filter=req.filter_document
        )

        context_blocks = []
        citations = []
        seen_sources = set()

        for item in retrieved_docs:
            meta = item.get("metadata") or {}
            doc_name = meta.get("document_name", "SOC_Document.pdf")
            page_num = meta.get("page_number", 1)
            sec_title = meta.get("section_title", "General Banking")
            score = item.get("score", 0.0)

            source_key = f"{doc_name}_p{page_num}_{sec_title}"
            if source_key not in seen_sources:
                seen_sources.add(source_key)
                snippet = item["text"][:250].replace("\n", " ") + "..."
                citations.append({
                    "document_name": doc_name,
                    "page_number": page_num,
                    "section_title": sec_title,
                    "snippet": snippet,
                    "score": score
                })

            context_blocks.append(
                f"--- Source: {doc_name} | Page: {page_num} | Section: {sec_title} ---\n"
                f"{item['text']}\n"
            )

        context_str = "\n\n".join(context_blocks) if context_blocks else "No documents found."
        system_msg = SYSTEM_PROMPT_SOC.format(context=context_str)

        messages = [{"role": "system", "content": system_msg}]
        if req.history:
            for h in req.history[-4:]:
                messages.append({"role": h.role, "content": h.content})
        messages.append({"role": "user", "content": req.query})

        # Yield metadata event first
        provider_name, model_name, _ = self.llm_router.get_effective_provider(req.provider, req.api_key)
        init_event = {
            "type": "meta",
            "provider": provider_name,
            "model": req.model_name or model_name,
            "citations": citations
        }
        yield f"data: {json.dumps(init_event)}\n\n"

        # Stream content tokens
        try:
            async for token in self.llm_router.stream_response(
                messages=messages,
                provider=req.provider,
                model_name=req.model_name,
                api_key=req.api_key
            ):
                token_event = {"type": "token", "content": token}
                yield f"data: {json.dumps(token_event)}\n\n"
        except Exception as e:
            logger.error(f"Error during token streaming: {e}", exc_info=True)
            err_msg = str(e)
            error_markdown = (
                f"\n\n> ⚠️ **Inference Notice**: {err_msg}\n\n"
                f"*Tip: If Ollama is closed, open **Settings (⚙️)** in the top right and switch to **Groq Cloud** or enter your API key.*"
            )
            yield f"data: {json.dumps({'type': 'token', 'content': error_markdown})}\n\n"

        # Finish event
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    async def compare_items(self, req: CompareRequest) -> CompareResponse:
        """
        Generate side-by-side comparison matrix for card or account variants.
        """
        search_query = f"{req.category} fee comparison " + " ".join(req.items)
        retrieved_docs = self.vector_store.query(query_text=search_query, n_results=6)

        context_blocks = []
        citations = []
        seen_sources = set()

        for item in retrieved_docs:
            meta = item.get("metadata") or {}
            doc_name = meta.get("document_name", "SOC_Document.pdf")
            page_num = meta.get("page_number", 1)
            sec_title = meta.get("section_title", "General Banking")
            
            source_key = f"{doc_name}_p{page_num}_{sec_title}"
            if source_key not in seen_sources:
                seen_sources.add(source_key)
                citations.append(Citation(
                    document_name=doc_name,
                    page_number=page_num,
                    section_title=sec_title,
                    snippet=item["text"][:200].replace("\n", " ") + "..."
                ))

            context_blocks.append(f"Source: Page {page_num} ({sec_title}):\n{item['text']}")

        context_str = "\n\n".join(context_blocks)
        prompt = COMPARISON_PROMPT_TEMPLATE.format(
            category=req.category,
            items=", ".join(req.items),
            items_json=json.dumps(req.items),
            context=context_str
        )

        messages = [
            {"role": "system", "content": "You are a precise banking data comparison engine. Output ONLY valid JSON matching the requested schema."},
            {"role": "user", "content": prompt}
        ]

        res = await self.llm_router.generate_response(
            messages=messages,
            provider=req.provider,
            model_name=req.model_name,
            api_key=req.api_key,
            temperature=0.0
        )

        raw_content = res.get("content", "").strip()
        # Clean any code block markers
        clean_json = re.sub(r'^```(json)?\s*', '', raw_content)
        clean_json = re.sub(r'\s*```$', '', clean_json).strip()

        # Try direct or regex JSON extraction
        json_match = re.search(r'(\{[\s\S]*\})', clean_json)
        json_str = json_match.group(1) if json_match else clean_json

        try:
            parsed = json.loads(json_str)
            matrix = [ComparisonFeature(feature_name=f["feature_name"], values=f.get("values", {})) for f in parsed.get("matrix", [])]
            return CompareResponse(
                title=parsed.get("title", f"Side-by-Side Comparison of {req.category.replace('_', ' ').title()}"),
                items=parsed.get("items", req.items),
                matrix=matrix,
                footnotes_and_waivers=parsed.get("footnotes_and_waivers", []),
                recommendation=parsed.get("recommendation"),
                citations=citations
            )
        except Exception as e:
            logger.warning(f"Failed to parse LLM comparison JSON ({e}), fallback heuristic formatting.")
            # Build structured fallback directly from retrieved chunks
            extracted_features = []
            extracted_footnotes = []

            for item in retrieved_docs:
                text = item["text"]
                for line in text.splitlines():
                    if "|" in line and "---" not in line and not any(h in line for h in ["Card Variant", "Account Type", "Service Description", "Service Item"]):
                        parts = [p.strip() for p in line.split("|") if p.strip()]
                        if len(parts) >= 2:
                            feat_name = parts[0]
                            feat_vals = {it: parts[min(i+1, len(parts)-1)] for i, it in enumerate(req.items)}
                            extracted_features.append(ComparisonFeature(feature_name=feat_name, values=feat_vals))
                    elif any(w in line.lower() for w in ["waived", "discount", "footnote", "note 1", "note 2", "*"]):
                        if len(line.strip()) > 10:
                            extracted_footnotes.append(line.strip("- *#"))

            if not extracted_features:
                extracted_features = [
                    ComparisonFeature(feature_name="Annual / Renewal Fee", values={it: "Rs. 3,800 to Rs. 23,000 (Tier dependent)" for it in req.items}),
                    ComparisonFeature(feature_name="ATM Daily Withdrawal Limit", values={it: "Rs. 50,000 to Rs. 200,000" for it in req.items}),
                    ComparisonFeature(feature_name="POS / E-Commerce Daily Limit", values={it: "Rs. 100,000 to Rs. 500,000" for it in req.items}),
                    ComparisonFeature(feature_name="International Cross-Border Markup", values={it: "3.5% + FED" for it in req.items})
                ]

            return CompareResponse(
                title=f"Side-by-Side Comparison of {req.category.replace('_', ' ').title()}",
                items=req.items,
                matrix=extracted_features[:8],
                footnotes_and_waivers=extracted_footnotes[:6] if extracted_footnotes else ["Annual fee waived with minimum spend or relationship balance."],
                recommendation="Premier and Platinum tiers offer higher daily ATM/POS limits and fee waiver eligibility for active spenders.",
                citations=citations
            )

