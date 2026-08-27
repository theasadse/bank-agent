import os
import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from fastembed import TextEmbedding

from backend.config import CHROMA_DIR, EMBEDDING_MODEL_NAME, CHROMA_COLLECTION_NAME
from backend.parser import ParsedChunk
from backend.models import Citation

logger = logging.getLogger("bank_soc.vector_store")
logging.basicConfig(level=logging.INFO)

class BankSOCVectorStore:
    """
    Vector Store powered by FastEmbed (BAAI/bge-small-en-v1.5) ONNX local runtime
    and ChromaDB persistent embedded database.
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
        logger.info(f"ChromaDB collection '{CHROMA_COLLECTION_NAME}' ready. Current items: {self.collection.count()}")

    def add_chunks(self, chunks: List[ParsedChunk]) -> int:
        """
        Embed and persist document chunks into ChromaDB.
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
            # Create a unique, deterministic ID
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
        logger.info(f"Successfully indexed {len(ids)} chunks in ChromaDB.")
        return len(ids)

    def query(self, query_text: str, n_results: int = 5, category_filter: Optional[str] = None, document_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Perform semantic similarity retrieval using FastEmbed query embedding.
        """
        query_embeddings = [emb.tolist() for emb in self.embedding_model.embed([query_text])]
        
        where_clause = {}
        if category_filter:
            where_clause["category"] = category_filter
        if document_filter:
            where_clause["document_name"] = document_filter

        query_args = {
            "query_embeddings": query_embeddings,
            "n_results": min(n_results, max(1, self.collection.count())),
            "include": ["documents", "metadatas", "distances"]
        }
        if where_clause:
            query_args["where"] = where_clause

        results = self.collection.query(**query_args)

        retrieved = []
        if results and results.get("documents") and len(results["documents"]) > 0:
            docs = results["documents"][0]
            metas = results["metadatas"][0] if (results.get("metadatas") and len(results["metadatas"]) > 0 and results["metadatas"][0]) else [{}] * len(docs)
            dists = results["distances"][0] if (results.get("distances") and len(results["distances"]) > 0 and results["distances"][0]) else [0.0] * len(docs)

            for doc, meta, dist in zip(docs, metas, dists):
                meta_clean = meta if isinstance(meta, dict) else {}
                retrieved.append({
                    "text": doc,
                    "metadata": meta_clean,
                    "distance": dist or 0.0,
                    "score": round(1.0 - ((dist or 0.0) / 2.0), 4) # Normalized similarity
                })

        return retrieved

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
        Remove all chunks belonging to a document from ChromaDB.
        """
        self.collection.delete(where={"document_name": document_name})
        return True

    def total_count(self) -> int:
        return self.collection.count()
