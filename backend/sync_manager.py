import os
import json
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple
from datetime import datetime

from backend.config import SAMPLE_DATA_DIR, UPLOADS_DIR, DATA_DIR
from backend.parser import BankSOCParser
from backend.vector_store import BankSOCVectorStore

logger = logging.getLogger("bank_soc.sync")
logging.basicConfig(level=logging.INFO)

MANIFEST_FILE = DATA_DIR / "index_manifest.json"

class DocumentSyncManager:
    """
    Automated Schedule of Charges (SOC) File Watcher & Synchronization Engine.
    Detects new, modified (biannual revisions), or removed SOC PDFs,
    and automatically re-runs chunking, footnote extraction, and ChromaDB indexing.
    """

    def __init__(self, parser: BankSOCParser, vector_store: BankSOCVectorStore):
        self.parser = parser
        self.vector_store = vector_store
        self.manifest = self._load_manifest()

    def _load_manifest(self) -> Dict[str, Any]:
        if MANIFEST_FILE.exists():
            try:
                with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error loading manifest: {e}")
        return {}

    def _save_manifest(self):
        try:
            with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
                json.dump(self.manifest, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving manifest: {e}")

    @staticmethod
    def compute_file_hash(file_path: Path) -> str:
        """Compute SHA256 hash of the PDF file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def sync_all(self) -> Dict[str, Any]:
        """
        Scans sample_data and uploads folders, detects changes,
        and automatically re-indexes changed or new PDFs.
        """
        all_pdf_paths: List[Path] = []
        if SAMPLE_DATA_DIR.exists():
            all_pdf_paths.extend(list(SAMPLE_DATA_DIR.glob("*.pdf")))
        if UPLOADS_DIR.exists():
            all_pdf_paths.extend(list(UPLOADS_DIR.glob("*.pdf")))

        current_file_names = {p.name for p in all_pdf_paths}
        manifest_file_names = set(self.manifest.keys())

        # 1. Identify Deleted PDFs and purge from ChromaDB
        deleted_files = manifest_file_names - current_file_names
        for del_name in deleted_files:
            logger.info(f"Detected removed SOC document: '{del_name}'. Purging from vector store...")
            self.vector_store.delete_document(del_name)
            del self.manifest[del_name]

        # 2. Check for New or Modified PDFs
        added_or_updated = []
        unchanged = []

        for pdf_path in all_pdf_paths:
            file_name = pdf_path.name
            file_hash = self.compute_file_hash(pdf_path)
            file_mtime = pdf_path.stat().st_mtime

            prev_entry = self.manifest.get(file_name)
            needs_reindex = False

            if not prev_entry:
                needs_reindex = True
                action = "new_document"
            elif prev_entry.get("file_hash") != file_hash:
                needs_reindex = True
                action = "content_updated"
            elif self.vector_store.total_count() == 0:
                needs_reindex = True
                action = "store_empty"

            if needs_reindex:
                logger.info(f"Re-indexing SOC PDF [{action}]: '{file_name}'...")
                # Delete previous version chunks if it existed
                if prev_entry:
                    self.vector_store.delete_document(file_name)

                # Parse and extract tables & footnotes
                chunks = self.parser.parse_pdf(pdf_path, document_name=file_name)
                count = self.vector_store.add_chunks(chunks)

                self.manifest[file_name] = {
                    "file_name": file_name,
                    "file_path": str(pdf_path),
                    "file_hash": file_hash,
                    "file_mtime": file_mtime,
                    "total_chunks": count,
                    "total_pages": max([c.page_number for c in chunks] or [1]),
                    "last_indexed_at": datetime.now().isoformat(),
                    "status": "ACTIVE"
                }
                added_or_updated.append({"file_name": file_name, "action": action, "chunks": count})
            else:
                unchanged.append(file_name)

        self._save_manifest()

        active_docs = self.vector_store.get_indexed_documents()
        return {
            "status": "SUCCESS",
            "updated_documents": added_or_updated,
            "deleted_documents": list(deleted_files),
            "unchanged_documents": unchanged,
            "total_active_chunks": self.vector_store.total_count(),
            "active_documents": active_docs
        }
