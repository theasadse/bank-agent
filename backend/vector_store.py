import os
import re
import math
import logging
from typing import List, Dict, Any, Optional
from collections import Counter
import chromadb
from chromadb.config import Settings
from fastembed import TextEmbedding

from backend.config import CHROMA_DIR, EMBEDDING_MODEL_NAME, CHROMA_COLLECTION_NAME
from backend.parser import ParsedChunk
from backend.models import Citation

logger = logging.getLogger("bank_soc.vector_store")
logging.basicConfig(level=logging.INFO)

class BM25Index:
    """
    Lightweight, high-performance in-memory Okapi BM25 sparse search index.
    Optimized for exact keyword and acronym matching (e.g. IBFT, PayPak, FED, WHT, Raast).
    """
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = 0
        self.avg_doc_len = 0.0
        self.doc_lens: List[int] = []
        self.doc_freqs: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.doc_term_counts: List[Counter] = []
        self.doc_ids: List[str] = []
        self.doc_metadatas: List[Dict[str, Any]] = []
        self.doc_texts: List[str] = []

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r'[a-zA-Z0-9_\-\.\%]+', text.lower())

    def build_index(self, doc_ids: List[str], doc_texts: List[str], doc_metadatas: List[Dict[str, Any]]):
        self.doc_ids = doc_ids
        self.doc_texts = doc_texts
        self.doc_metadatas = doc_metadatas
        self.corpus_size = len(doc_texts)
        self.doc_lens = []
        self.doc_term_counts = []
        self.doc_freqs = {}

        if self.corpus_size == 0:
            self.avg_doc_len = 0.0
            self.idf = {}
            return

        total_len = 0
        for text in doc_texts:
            tokens = self._tokenize(text)
            doc_len = len(tokens)
            self.doc_lens.append(doc_len)
            total_len += doc_len
            
            term_counts = Counter(tokens)
            self.doc_term_counts.append(term_counts)
            
            for term in term_counts.keys():
                self.doc_freqs[term] = self.doc_freqs.get(term, 0) + 1

        self.avg_doc_len = total_len / self.corpus_size if self.corpus_size > 0 else 0.0

        # Calculate IDF with smoothing
        self.idf = {}
        for term, freq in self.doc_freqs.items():
            self.idf[term] = math.log(1.0 + (self.corpus_size - freq + 0.5) / (freq + 0.5))

    def search(
        self,
        query: str,
        n_results: int = 10,
        category_filter: Optional[str] = None,
        document_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if self.corpus_size == 0:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores = []
        for idx in range(self.corpus_size):
            meta = self.doc_metadatas[idx] if idx < len(self.doc_metadatas) else {}
            
            # Apply filters
            if category_filter and meta.get("category") != category_filter:
                continue
            if document_filter and meta.get("document_name") != document_filter:
                continue

            doc_len = self.doc_lens[idx]
            term_counts = self.doc_term_counts[idx]
            score = 0.0

            for q_term in query_tokens:
                if q_term not in term_counts:
                    continue
                tf = term_counts[q_term]
                idf = self.idf.get(q_term, 0.0)
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * (doc_len / (self.avg_doc_len or 1.0)))
                score += idf * (numerator / denominator)

            if score > 0.0:
                scores.append({
                    "id": self.doc_ids[idx],
                    "text": self.doc_texts[idx],
                    "metadata": meta,
                    "bm25_score": score
                })

        scores.sort(key=lambda x: x["bm25_score"], reverse=True)
        return scores[:n_results]


class BankSOCVectorStore:
    """
    Hybrid Vector Store powered by:
    1. FastEmbed (BAAI/bge-small-en-v1.5) ONNX local runtime for dense semantic vectors.
    2. BM25 Okapi sparse keyword index for exact fee codes & acronyms.
    3. ChromaDB persistent embedded database.
    4. Reciprocal Rank Fusion (RRF) for merged, high-precision retrieval.
    """

    def __init__(self):
        logger.info(f"Initializing FastEmbed model: {EMBEDDING_MODEL_NAME}...")
        self.embedding_model = TextEmbedding(model_name=EMBEDDING_MODEL_NAME)
        
        logger.info(f"Connecting to ChromaDB at {CHROMA_DIR}...")
        self.chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        self.collection = self.chroma_client.get_or_create_collection(
            name=CHROMA_COLLECTION_NAME,
            metadata={"description": "Schedule of Charges and Banking Fees Knowledge Base"}
        )
        self.bm25 = BM25Index()
        self._refresh_bm25_index()
        logger.info(f"ChromaDB & BM25 Hybrid collection '{CHROMA_COLLECTION_NAME}' ready. Current items: {self.collection.count()}")

    def _refresh_bm25_index(self):
        """
        Reconstructs the in-memory BM25 index from ChromaDB documents.
        """
        try:
            all_docs = self.collection.get(include=["documents", "metadatas"])
            if all_docs and all_docs.get("ids"):
                ids = all_docs["ids"]
                texts = all_docs.get("documents") or []
                metas = all_docs.get("metadatas") or []
                self.bm25.build_index(ids, texts, metas)
                logger.info(f"BM25 index built with {len(ids)} chunks.")
            else:
                self.bm25.build_index([], [], [])
        except Exception as e:
            logger.error(f"Error rebuilding BM25 index: {e}")

    def add_chunks(self, chunks: List[ParsedChunk]) -> int:
        """
        Embed and persist document chunks into ChromaDB and update the BM25 index.
        """
        if not chunks:
            return 0

        texts = [chunk.text for chunk in chunks]
        logger.info(f"Generating embeddings for {len(texts)} chunks via FastEmbed...")
        embeddings = [emb.tolist() for emb in self.embedding_model.embed(texts)]

        ids = []
        metadatas = []
        documents = []

        for idx, chunk in enumerate(chunks):
            chunk_id = f"{chunk.document_name}_p{chunk.page_number}_c{idx}"
            ids.append(chunk_id)
            documents.append(chunk.text)
            
            meta = {
                "document_name": chunk.document_name,
                "page_number": int(chunk.page_number),
                "section_title": str(chunk.section_title),
                "category": str(chunk.category),
                "has_tables": bool(chunk.has_tables),
                "has_footnotes": bool(chunk.has_footnotes),
            }
            metadatas.append(meta)

        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )
        self._refresh_bm25_index()
        logger.info(f"Successfully indexed {len(ids)} chunks in ChromaDB and refreshed BM25 index.")
        return len(ids)

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        category_filter: Optional[str] = None,
        document_filter: Optional[str] = None,
        use_hybrid: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Perform Hybrid Retrieval:
        1. Dense Vector Search via FastEmbed & ChromaDB.
        2. Sparse BM25 Keyword Search.
        3. Reciprocal Rank Fusion (RRF) to combine candidate rankings.
        """
        total_items = self.collection.count()
        if total_items == 0:
            return []

        # 1. Dense Vector Retrieval
        query_embeddings = [emb.tolist() for emb in self.embedding_model.embed([query_text])]
        where_clause = {}
        if category_filter:
            where_clause["category"] = category_filter
        if document_filter:
            where_clause["document_name"] = document_filter

        fetch_k = min(max(n_results * 3, 10), total_items)
        query_args = {
            "query_embeddings": query_embeddings,
            "n_results": fetch_k,
            "include": ["documents", "metadatas", "distances"]
        }
        if where_clause:
            query_args["where"] = where_clause

        chroma_res = self.collection.query(**query_args)

        dense_ranked = []
        if chroma_res and chroma_res.get("documents") and len(chroma_res["documents"]) > 0:
            docs = chroma_res["documents"][0]
            metas = chroma_res["metadatas"][0] if (chroma_res.get("metadatas") and len(chroma_res["metadatas"]) > 0) else [{}] * len(docs)
            dists = chroma_res["distances"][0] if (chroma_res.get("distances") and len(chroma_res["distances"]) > 0) else [0.0] * len(docs)
            ids = chroma_res["ids"][0] if (chroma_res.get("ids") and len(chroma_res["ids"]) > 0) else [f"doc_{i}" for i in range(len(docs))]

            for doc_id, doc, meta, dist in zip(ids, docs, metas, dists):
                dense_ranked.append({
                    "id": doc_id,
                    "text": doc,
                    "metadata": meta if isinstance(meta, dict) else {},
                    "distance": dist or 0.0,
                    "vector_score": round(1.0 - ((dist or 0.0) / 2.0), 4)
                })

        if not use_hybrid:
            return dense_ranked[:n_results]

        # 2. Sparse BM25 Keyword Retrieval
        bm25_ranked = self.bm25.search(
            query=query_text,
            n_results=fetch_k,
            category_filter=category_filter,
            document_filter=document_filter
        )

        # 3. Reciprocal Rank Fusion (RRF)
        # RRF formula: Score(d) = SUM_{r in {dense, bm25}} 1.0 / (k + rank(d, r))
        RRF_K = 60
        fused_scores: Dict[str, float] = {}
        doc_map: Dict[str, Dict[str, Any]] = {}

        for rank, item in enumerate(dense_ranked):
            doc_id = item["id"]
            doc_map[doc_id] = item
            fused_scores[doc_id] = fused_scores.get(doc_id, 0.0) + (1.0 / (RRF_K + rank + 1))

        for rank, item in enumerate(bm25_ranked):
            doc_id = item["id"]
            if doc_id not in doc_map:
                doc_map[doc_id] = item
            fused_scores[doc_id] = fused_scores.get(doc_id, 0.0) + (1.0 / (RRF_K + rank + 1))

        # Sort combined results by RRF score
        sorted_ids = sorted(fused_scores.keys(), key=lambda x: fused_scores[x], reverse=True)
        
        final_results = []
        for doc_id in sorted_ids[:n_results]:
            item = doc_map[doc_id]
            rrf_score = fused_scores[doc_id]
            
            # Normalize confidence score
            confidence = min(0.99, round(rrf_score * 30.0 + (item.get("vector_score", 0.5) * 0.5), 4))
            
            final_results.append({
                "id": doc_id,
                "text": item["text"],
                "metadata": item["metadata"],
                "score": confidence,
                "rrf_score": round(rrf_score, 5)
            })

        return final_results

    def get_indexed_documents(self) -> List[Dict[str, Any]]:
        """
        List all distinct documents indexed with their chunk count and page count.
        """
        all_data = self.collection.get(include=["metadatas"])
        if not all_data or not all_data.get("metadatas"):
            return []

        doc_stats: Dict[str, Dict[str, Any]] = {}
        for meta in all_data["metadatas"]:
            doc_name = meta.get("document_name", "Unknown")
            page_num = meta.get("page_number", 1)
            if doc_name not in doc_stats:
                doc_stats[doc_name] = {
                    "document_name": doc_name,
                    "total_chunks": 0,
                    "pages": set(),
                    "categories": set()
                }
            doc_stats[doc_name]["total_chunks"] += 1
            doc_stats[doc_name]["pages"].add(page_num)
            if meta.get("category"):
                doc_stats[doc_name]["categories"].add(meta.get("category"))

        summary = []
        for doc_name, stat in doc_stats.items():
            summary.append({
                "document_name": doc_name,
                "total_chunks": stat["total_chunks"],
                "total_pages": len(stat["pages"]),
                "categories": list(stat["categories"])
            })
        return summary

    def delete_document(self, document_name: str) -> bool:
        """
        Remove all chunks belonging to a document from ChromaDB and refresh the BM25 index.
        """
        self.collection.delete(where={"document_name": document_name})
        self._refresh_bm25_index()
        return True

    def total_count(self) -> int:
        return self.collection.count()
