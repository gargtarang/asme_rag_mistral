"""
ASME RAG Storage Module

This module provides SQLite storage with FTS5 for efficient retrieval.
It handles:
- Chunk storage with metadata
- Embedding storage
- FTS5 full-text search
- Cross-reference indexing
"""

import os
import sys
import sqlite3
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import hashlib

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asme_rag.utils import Config, get_config, ChunkMetadata


@dataclass
class StorageStats:
    """Statistics about the storage."""
    chunk_count: int = 0
    doc_count: int = 0
    embedding_count: int = 0
    total_pages: int = 0
    
    def to_dict(self) -> Dict[str, int]:
        return {
            'chunk_count': self.chunk_count,
            'doc_count': self.doc_count,
            'embedding_count': self.embedding_count,
            'total_pages': self.total_pages
        }


class Storage:
    """
    SQLite storage for ASME RAG system.
    
    Provides:
    - Chunk storage with metadata
    - Embedding storage
    - FTS5 full-text search
    - Cross-reference indexing
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the storage.
        
        Args:
            config: Configuration object
        """
        self.config = config or get_config()
        self.logger = logging.getLogger(__name__)
        self.conn = None
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize the SQLite database and create tables."""
        # Ensure directory exists
        db_dir = os.path.dirname(self.config.database_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        
        # Connect to database
        self.conn = sqlite3.connect(self.config.database_path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        
        # Create tables
        self._create_tables()
        
        self.logger.info(f"Database initialized at {self.config.database_path}")
    
    def _create_tables(self):
        """Create database tables."""
        cursor = self.conn.cursor()
        
        # Documents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                code TEXT NOT NULL,
                division TEXT,
                edition INTEGER NOT NULL,
                unit_system TEXT,
                pdf_path TEXT,
                parser_profile TEXT,
                chunker_profile TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Chunks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                code TEXT NOT NULL,
                division TEXT,
                edition INTEGER NOT NULL,
                part_or_subsection TEXT,
                clause_id TEXT,
                pdf_page INTEGER NOT NULL,
                type TEXT NOT NULL,
                model_generated BOOLEAN DEFAULT FALSE,
                verified BOOLEAN DEFAULT FALSE,
                status TEXT DEFAULT 'mandatory',
                heading_path TEXT,
                bold_flags TEXT,
                text TEXT NOT NULL,
                content_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
            )
        """)
        
        # Create index on chunks for faster lookup
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_doc_clause 
            ON chunks(doc_id, clause_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_page 
            ON chunks(pdf_page)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_type 
            ON chunks(type)
        """)
        
        # Embeddings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                chunk_id TEXT PRIMARY KEY,
                embedding BLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chunk_id) REFERENCES chunks(chunk_id)
            )
        """)
        
        # FTS5 table for full-text search
        fts5_config = self.config.fts5_tokenize
        cursor.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts 
            USING fts5(
                chunk_id UNINDEXED,
                doc_id UNINDEXED,
                code UNINDEXED,
                division UNINDEXED,
                edition UNINDEXED,
                clause_id UNINDEXED,
                pdf_page UNINDEXED,
                type UNINDEXED,
                text,
                tokenize="{fts5_config}"
            )
        """)
        
        # Cross-references table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cross_references (
                ref_id TEXT PRIMARY KEY,
                from_chunk_id TEXT NOT NULL,
                from_clause_id TEXT,
                kind TEXT NOT NULL,
                target TEXT NOT NULL,
                target_clause_id TEXT,
                target_doc_id TEXT,
                certainty TEXT DEFAULT 'certain',
                status TEXT DEFAULT 'resolved',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (from_chunk_id) REFERENCES chunks(chunk_id)
            )
        """)
        
        # Figures table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS figures (
                figure_id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                page INTEGER NOT NULL,
                bbox_x REAL,
                bbox_y REAL,
                bbox_width REAL,
                bbox_height REAL,
                caption TEXT,
                figure_number TEXT,
                description TEXT,
                model_generated BOOLEAN DEFAULT FALSE,
                verified BOOLEAN DEFAULT FALSE,
                content_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
            )
        """)
        
        # Note: FTS5 virtual tables cannot have additional indexes in SQLite
        # The FTS5 table itself provides full-text search capability
        
        self.conn.commit()
    
    def store_chunks(self, chunks: List[ChunkMetadata]) -> int:
        """
        Store chunks in the database.
        
        Args:
            chunks: List of ChunkMetadata objects
            
        Returns:
            Number of chunks stored
        """
        if not chunks:
            return 0
        
        cursor = self.conn.cursor()
        stored_count = 0
        
        for chunk in chunks:
            # Check if chunk already exists
            cursor.execute(
                "SELECT 1 FROM chunks WHERE chunk_id = ?",
                (chunk.content_hash,)
            )
            
            if cursor.fetchone():
                # Chunk already exists, skip
                continue
            
            # Insert chunk
            cursor.execute("""
                INSERT INTO chunks (
                    chunk_id, doc_id, code, division, edition, 
                    part_or_subsection, clause_id, pdf_page, type,
                    model_generated, verified, status, heading_path, bold_flags, text, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chunk.content_hash,
                chunk.doc_id,
                chunk.code,
                chunk.division,
                chunk.edition,
                chunk.part_or_subsection,
                chunk.clause_id,
                chunk.pdf_page,
                chunk.type,
                chunk.model_generated,
                chunk.verified,
                chunk.status,
                chunk.heading_path,
                chunk.bold_flags,
                chunk.text,
                chunk.content_hash
            ))
            
            # Insert into FTS table
            cursor.execute("""
                INSERT INTO chunks_fts (
                    chunk_id, doc_id, code, division, edition, 
                    clause_id, pdf_page, type, text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chunk.content_hash,
                chunk.doc_id,
                chunk.code,
                chunk.division,
                chunk.edition,
                chunk.clause_id,
                chunk.pdf_page,
                chunk.type,
                chunk.text
            ))
            
            stored_count += 1
        
        self.conn.commit()
        self.logger.info(f"Stored {stored_count} chunks")
        return stored_count
    
    def store_embedding(self, chunk_id: str, embedding: List[float]) -> bool:
        """
        Store an embedding for a chunk.
        
        Args:
            chunk_id: Chunk identifier
            embedding: List of float values (embedding vector)
            
        Returns:
            True if stored successfully
        """
        cursor = self.conn.cursor()
        
        # Convert embedding to bytes
        embedding_bytes = np.array(embedding, dtype=np.float32).tobytes()
        
        cursor.execute("""
            INSERT OR REPLACE INTO embeddings (chunk_id, embedding) 
            VALUES (?, ?)
        """, (chunk_id, embedding_bytes))
        
        self.conn.commit()
        return True
    
    def store_embeddings(self, embeddings: Dict[str, List[float]]) -> int:
        """
        Store multiple embeddings.
        
        Args:
            embeddings: Dictionary mapping chunk_id to embedding vector
            
        Returns:
            Number of embeddings stored
        """
        cursor = self.conn.cursor()
        stored_count = 0
        
        for chunk_id, embedding in embeddings.items():
            embedding_bytes = np.array(embedding, dtype=np.float32).tobytes()
            cursor.execute("""
                INSERT OR REPLACE INTO embeddings (chunk_id, embedding) 
                VALUES (?, ?)
            """, (chunk_id, embedding_bytes))
            stored_count += 1
        
        self.conn.commit()
        self.logger.info(f"Stored {stored_count} embeddings")
        return stored_count
    
    def get_chunks_by_clause(self, clause_id: str) -> List[Dict[str, Any]]:
        """
        Get chunks by clause ID.
        
        Args:
            clause_id: Clause identifier
            
        Returns:
            List of chunk dictionaries
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT * FROM chunks 
            WHERE clause_id = ? 
            ORDER BY pdf_page, chunk_id
        """, (clause_id,))
        
        columns = [col[0] for col in cursor.description]
        chunks = []
        
        for row in cursor.fetchall():
            chunk_dict = dict(zip(columns, row))
            chunks.append(chunk_dict)
        
        return chunks
    
    def get_chunks_by_doc(self, doc_id: str) -> List[Dict[str, Any]]:
        """
        Get chunks by document ID.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            List of chunk dictionaries
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT * FROM chunks 
            WHERE doc_id = ? 
            ORDER BY pdf_page, chunk_id
        """, (doc_id,))
        
        columns = [col[0] for col in cursor.description]
        chunks = []
        
        for row in cursor.fetchall():
            chunk_dict = dict(zip(columns, row))
            chunks.append(chunk_dict)
        
        return chunks
    
    def get_chunks_by_part(self, part: str) -> List[Dict[str, Any]]:
        """
        Get chunks by part or subsection.
        
        Args:
            part: Part or subsection identifier
            
        Returns:
            List of chunk dictionaries
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT * FROM chunks 
            WHERE part_or_subsection = ? 
            ORDER BY pdf_page, chunk_id
        """, (part,))
        
        columns = [col[0] for col in cursor.description]
        chunks = []
        
        for row in cursor.fetchall():
            chunk_dict = dict(zip(columns, row))
            chunks.append(chunk_dict)
        
        return chunks
    
    def search_chunks(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Search chunks using FTS5.
        
        Args:
            query: Search query
            filters: Optional filters (doc_id, code, edition, etc.)
            
        Returns:
            List of matching chunk dictionaries
        """
        cursor = self.conn.cursor()
        
        # Build FTS query
        fts_query = query
        
        # Add filters to FTS query
        filter_conditions = []
        if filters:
            if 'doc_id' in filters:
                filter_conditions.append(f"doc_id = '{filters['doc_id']}'")
            if 'code' in filters:
                filter_conditions.append(f"code = '{filters['code']}'")
            if 'edition' in filters:
                filter_conditions.append(f"edition = {filters['edition']}")
            if 'clause_id' in filters:
                filter_conditions.append(f"clause_id = '{filters['clause_id']}'")
        
        filter_clause = " AND ".join(filter_conditions) if filter_conditions else "1"
        
        # Execute FTS search
        cursor.execute(f"""
            SELECT * FROM chunks_fts 
            WHERE chunks_fts MATCH ? AND {filter_clause}
            ORDER BY rank
            LIMIT {self.config.top_k}
        """, (fts_query,))
        
        # Get chunk IDs from FTS results
        chunk_ids = [row[0] for row in cursor.fetchall()]
        
        if not chunk_ids:
            return []
        
        # Get full chunk data
        chunk_ids_str = ",".join([f"'{cid}'" for cid in chunk_ids])
        cursor.execute(f"""
            SELECT * FROM chunks 
            WHERE chunk_id IN ({chunk_ids_str})
            ORDER BY pdf_page, chunk_id
        """)
        
        columns = [col[0] for col in cursor.description]
        chunks = []
        
        for row in cursor.fetchall():
            chunk_dict = dict(zip(columns, row))
            chunks.append(chunk_dict)
        
        return chunks
    
    def get_embedding(self, chunk_id: str) -> Optional[List[float]]:
        """
        Get embedding for a chunk.
        
        Args:
            chunk_id: Chunk identifier
            
        Returns:
            Embedding vector or None
        """
        cursor = self.conn.cursor()
        
        cursor.execute(
            "SELECT embedding FROM embeddings WHERE chunk_id = ?",
            (chunk_id,)
        )
        
        row = cursor.fetchone()
        if row and row[0]:
            embedding_bytes = row[0]
            embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
            return embedding.tolist()
        
        return None
    
    def get_embeddings(self, chunk_ids: List[str]) -> Dict[str, List[float]]:
        """
        Get embeddings for multiple chunks.
        
        Args:
            chunk_ids: List of chunk identifiers
            
        Returns:
            Dictionary mapping chunk_id to embedding vector
        """
        cursor = self.conn.cursor()
        
        embeddings = {}
        
        for chunk_id in chunk_ids:
            cursor.execute(
                "SELECT embedding FROM embeddings WHERE chunk_id = ?",
                (chunk_id,)
            )
            
            row = cursor.fetchone()
            if row and row[0]:
                embedding_bytes = row[0]
                embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
                embeddings[chunk_id] = embedding.tolist()
        
        return embeddings
    
    def store_cross_reference(self, from_chunk_id: str, kind: str, target: str, 
                             certainty: str = 'certain', status: str = 'resolved',
                             from_clause_id: Optional[str] = None,
                             target_clause_id: Optional[str] = None,
                             target_doc_id: Optional[str] = None) -> bool:
        """
        Store a cross-reference.
        
        Args:
            from_chunk_id: Source chunk ID
            kind: Type of reference (clause, table, figure, etc.)
            target: Target identifier
            certainty: Certainty level (certain/fuzzy)
            status: Status (resolved/unresolved)
            from_clause_id: Source clause ID
            target_clause_id: Target clause ID
            target_doc_id: Target document ID
            
        Returns:
            True if stored successfully
        """
        cursor = self.conn.cursor()
        
        ref_id = hashlib.sha256(f"{from_chunk_id}:{kind}:{target}".encode()).hexdigest()[:16]
        
        cursor.execute("""
            INSERT OR REPLACE INTO cross_references (
                ref_id, from_chunk_id, from_clause_id, kind, target,
                target_clause_id, target_doc_id, certainty, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ref_id, from_chunk_id, from_clause_id, kind, target,
            target_clause_id, target_doc_id, certainty, status
        ))
        
        self.conn.commit()
        return True
    
    def get_cross_references(self, from_chunk_id: Optional[str] = None,
                           target: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get cross-references.
        
        Args:
            from_chunk_id: Filter by source chunk ID
            target: Filter by target
            
        Returns:
            List of cross-reference dictionaries
        """
        cursor = self.conn.cursor()
        
        conditions = []
        params = []
        
        if from_chunk_id:
            conditions.append("from_chunk_id = ?")
            params.append(from_chunk_id)
        
        if target:
            conditions.append("target = ?")
            params.append(target)
        
        where_clause = " AND ".join(conditions) if conditions else "1"
        
        cursor.execute(f"""
            SELECT * FROM cross_references 
            WHERE {where_clause}
            ORDER BY from_chunk_id, target
        """, params)
        
        columns = [col[0] for col in cursor.description]
        refs = []
        
        for row in cursor.fetchall():
            ref_dict = dict(zip(columns, row))
            refs.append(ref_dict)
        
        return refs
    
    def store_figure(self, figure_data: Dict[str, Any]) -> bool:
        """
        Store a figure description.
        
        Args:
            figure_data: Figure data dictionary
            
        Returns:
            True if stored successfully
        """
        cursor = self.conn.cursor()
        
        # Generate figure ID
        figure_id = hashlib.sha256(
            f"{figure_data.get('doc_id')}:{figure_data.get('page')}:{figure_data.get('bbox', (0,0,0,0))}".encode()
        ).hexdigest()[:16]
        
        bbox = figure_data.get('bbox', (0, 0, 0, 0))
        
        cursor.execute("""
            INSERT OR REPLACE INTO figures (
                figure_id, doc_id, page, bbox_x, bbox_y, bbox_width, bbox_height,
                caption, figure_number, description, model_generated, verified, content_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            figure_id,
            figure_data.get('doc_id'),
            figure_data.get('page'),
            bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1],
            figure_data.get('caption'),
            figure_data.get('figure_number'),
            figure_data.get('description'),
            figure_data.get('model_generated', False),
            figure_data.get('verified', False),
            figure_data.get('content_hash', figure_id)
        ))
        
        self.conn.commit()
        return True
    
    def get_figure(self, figure_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a figure by ID.
        
        Args:
            figure_id: Figure identifier
            
        Returns:
            Figure dictionary or None
        """
        cursor = self.conn.cursor()
        
        cursor.execute(
            "SELECT * FROM figures WHERE figure_id = ?",
            (figure_id,)
        )
        
        row = cursor.fetchone()
        if row:
            columns = [col[0] for col in cursor.description]
            return dict(zip(columns, row))
        
        return None
    
    def get_figures_by_page(self, doc_id: str, page: int) -> List[Dict[str, Any]]:
        """
        Get figures by document and page.
        
        Args:
            doc_id: Document identifier
            page: Page number
            
        Returns:
            List of figure dictionaries
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT * FROM figures 
            WHERE doc_id = ? AND page = ?
            ORDER BY bbox_y, bbox_x
        """, (doc_id, page))
        
        columns = [col[0] for col in cursor.description]
        figures = []
        
        for row in cursor.fetchall():
            figures.append(dict(zip(columns, row)))
        
        return figures
    
    def get_statistics(self) -> StorageStats:
        """
        Get database statistics.
        
        Returns:
            StorageStats object
        """
        cursor = self.conn.cursor()
        
        # Get chunk count
        cursor.execute("SELECT COUNT(*) FROM chunks")
        chunk_count = cursor.fetchone()[0]
        
        # Get document count
        cursor.execute("SELECT COUNT(*) FROM documents")
        doc_count = cursor.fetchone()[0]
        
        # Get embedding count
        cursor.execute("SELECT COUNT(*) FROM embeddings")
        embedding_count = cursor.fetchone()[0]
        
        # Get total pages
        cursor.execute("SELECT COUNT(DISTINCT pdf_page) FROM chunks")
        total_pages = cursor.fetchone()[0]
        
        return {
            'chunk_count': chunk_count,
            'doc_count': doc_count,
            'embedding_count': embedding_count,
            'total_pages': total_pages
        }
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Test function for the module
if __name__ == '__main__':
    from asme_rag.utils import get_config
    
    config = get_config()
    storage = Storage(config)
    
    # Test database creation
    print("Testing storage module...")
    
    # Create a test chunk
    test_chunk = ChunkMetadata(
        doc_id="test_doc",
        code="ASME BPVC",
        division="VIII-1",
        edition=2025,
        part_or_subsection="Part UG",
        clause_id="UG-37",
        pdf_page=123,
        type="text",
        text="This is a test chunk for UG-37 design rules.",
        model_generated=False,
        verified=False,
        status="mandatory"
    )
    
    # Store the chunk
    storage.store_chunks([test_chunk])
    print(f"Stored test chunk: {test_chunk.content_hash}")
    
    # Retrieve the chunk
    chunks = storage.get_chunks_by_clause("UG-37")
    print(f"Retrieved {len(chunks)} chunks for UG-37")
    
    # Test statistics
    stats = storage.get_statistics()
    print(f"Database statistics: {stats.to_dict()}")
    
    # Clean up
    storage.close()
    
    print("Storage module tests completed successfully!")
