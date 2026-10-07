"""
ASME RAG Retrieval and Generation Module

This module provides the core RAG functionality including:
- Hybrid retrieval (SQLite FTS5 + embedding similarity)
- Grounded answer generation
- Citation checking
- Model evaluation
"""

import os
import sys
import json
import logging
import time
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asme_rag.utils import Config, get_config, ChunkMetadata, RetrievalResult, Citation, parse_citations_from_text
from asme_rag.storage import Storage


@dataclass
class GroundedAnswer:
    """A grounded answer with citations."""
    
    question: str
    answer: str
    citations: List[Citation] = field(default_factory=list)
    excerpts: List[RetrievalResult] = field(default_factory=list)
    unverified_citations: List[Citation] = field(default_factory=list)
    needs_input: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'question': self.question,
            'answer': self.answer,
            'citations': [c.to_string() for c in self.citations],
            'excerpts': [e.to_dict() for e in self.excerpts],
            'unverified_citations': [c.to_string() for c in self.unverified_citations],
            'needs_input': self.needs_input
        }


class RAGSystem:
    """
    Retrieval-Augmented Generation system for ASME documents.
    
    Provides:
    - Hybrid retrieval (keyword + embedding)
    - Grounded answer generation
    - Citation checking
    - Materials lookup
    """
    
    # System prompt for the chat model
    SYSTEM_PROMPT = """
You are an offline assistant for the ASME Boiler and Pressure Vessel Code and related ASME standards.

Answer ONLY from the numbered excerpts provided.

Cite every statement as [code, edition, clause, PDF p.N].

If the excerpts do not contain the answer, reply "not found" and name the book, part or section where to look.

Never invent equations, constants, table values or clause numbers.

Flag any table or equation that looks garbled in the excerpt.

Do not perform final design calculations and never output design numbers; show the equations, the methodology and every input needed (for example thicknesses, membrane, primary and secondary stresses) so the calculator can compute them.

If a paragraph refers to another book or part, quote the reference and say whether that book is in the excerpts.

If information is missing or ambiguous, list it under NEEDS INPUT instead of assuming.

End with a line starting "Verify:" telling the user what to check in the real code.
"""
    
    def __init__(self, config: Optional[Config] = None, storage: Optional[Storage] = None):
        """
        Initialize the RAG system.
        
        Args:
            config: Configuration object
            storage: Storage instance
        """
        self.config = config or get_config()
        self.storage = storage or Storage(self.config)
        self.logger = logging.getLogger(__name__)
        
        # Check if we can connect to LM Studio
        self.lm_studio_available = self.check_lm_studio()
    
    def check_lm_studio(self) -> bool:
        """Check if LM Studio is available."""
        try:
            import requests
            try:
                response = requests.get(
                    f"{self.config.api_url}/models",
                    timeout=5
                )
                return response.status_code == 200
            except:
                return False
        except ImportError:
            return False
    
    def search(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[RetrievalResult]:
        """
        Perform hybrid retrieval search.
        
        Args:
            query: Search query
            filters: Optional filters (doc_id, code, edition, etc.)
            
        Returns:
            List of RetrievalResult objects
        """
        # Keyword search using FTS5
        keyword_results = self.keyword_search(query, filters)
        
        # Embedding search (if embeddings are available)
        embedding_results = []
        if self.lm_studio_available:
            try:
                embedding_results = self.embedding_search(query, filters)
            except Exception as e:
                self.logger.warning(f"Embedding search failed: {str(e)}")
        
        # Merge and rank results
        merged_results = self.merge_results(keyword_results, embedding_results)
        
        return merged_results[:self.config.top_k]
    
    def keyword_search(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[RetrievalResult]:
        """
        Perform keyword search using FTS5.
        
        Args:
            query: Search query
            filters: Optional filters
            
        Returns:
            List of RetrievalResult objects
        """
        chunks = self.storage.search_chunks(query, filters)
        
        results = []
        for chunk in chunks:
            result = RetrievalResult(
                chunk_id=chunk['chunk_id'],
                doc_id=chunk['doc_id'],
                code=chunk['code'],
                division=chunk['division'],
                edition=chunk['edition'],
                clause_id=chunk['clause_id'],
                pdf_page=chunk['pdf_page'],
                type=chunk['type'],
                text=chunk['text'],
                score=1.0  # FTS5 score, will be adjusted in merge
            )
            results.append(result)
        
        return results
    
    def embedding_search(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[RetrievalResult]:
        """
        Perform embedding-based search.
        
        Args:
            query: Search query
            filters: Optional filters
            
        Returns:
            List of RetrievalResult objects
        """
        # Get embedding for the query
        query_embedding = self.get_query_embedding(query)
        
        if query_embedding is None:
            return []
        
        # Get all chunk embeddings
        cursor = self.storage.conn.cursor()
        cursor.execute("SELECT chunk_id FROM chunks")
        all_chunk_ids = [row[0] for row in cursor.fetchall()]
        
        # Get embeddings for all chunks
        embeddings = self.storage.get_embeddings(all_chunk_ids)
        
        # Calculate similarity scores
        results = []
        for chunk_id, embedding in embeddings.items():
            if chunk_id in all_chunk_ids:
                similarity = self.cosine_similarity(query_embedding, embedding)
                
                # Get chunk metadata
                cursor.execute(
                    "SELECT * FROM chunks WHERE chunk_id = ?",
                    (chunk_id,)
                )
                row = cursor.fetchone()
                if row:
                    columns = [col[0] for col in cursor.description]
                    chunk_data = dict(zip(columns, row))
                    
                    result = RetrievalResult(
                        chunk_id=chunk_data['chunk_id'],
                        doc_id=chunk_data['doc_id'],
                        code=chunk_data['code'],
                        division=chunk_data['division'],
                        edition=chunk_data['edition'],
                        clause_id=chunk_data['clause_id'],
                        pdf_page=chunk_data['pdf_page'],
                        type=chunk_data['type'],
                        text=chunk_data['text'],
                        score=similarity
                    )
                    results.append(result)
        
        # Sort by similarity
        results.sort(key=lambda r: r.score, reverse=True)
        
        return results
    
    def get_query_embedding(self, query: str) -> Optional[List[float]]:
        """
        Get embedding for a query.
        
        Args:
            query: Query text
            
        Returns:
            Embedding vector or None
        """
        if not self.lm_studio_available:
            return None
        
        try:
            import requests
            import json
            
            # Prepare request
            url = f"{self.config.api_url}/embeddings"
            payload = {
                "input": f"{self.config.query_prefix}{query}",
                "model": self.config.embedding_model
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            # Send request
            response = requests.post(url, json=payload, headers=headers, timeout=self.config.timeout_seconds)
            
            if response.status_code == 200:
                data = response.json()
                embedding = data['data'][0]['embedding']
                return embedding
            else:
                self.logger.warning(f"Embedding request failed: {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.warning(f"Failed to get query embedding: {str(e)}")
            return None
    
    def cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            a: First vector
            b: Second vector
            
        Returns:
            Cosine similarity (0 to 1)
        """
        a_np = np.array(a, dtype=np.float32)
        b_np = np.array(b, dtype=np.float32)
        
        dot_product = np.dot(a_np, b_np)
        norm_a = np.linalg.norm(a_np)
        norm_b = np.linalg.norm(b_np)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return float(dot_product / (norm_a * norm_b))
    
    def merge_results(self, keyword_results: List[RetrievalResult], 
                     embedding_results: List[RetrievalResult]) -> List[RetrievalResult]:
        """
        Merge and rank results from keyword and embedding searches.
        
        Args:
            keyword_results: Results from keyword search
            embedding_results: Results from embedding search
            
        Returns:
            Merged and ranked results
        """
        # Create a dictionary of all results
        all_results = {}
        
        # Add keyword results
        for i, result in enumerate(keyword_results):
            if result.chunk_id not in all_results:
                # Normalize keyword score to 0-1 range
                normalized_score = 1.0 - (i / len(keyword_results)) if keyword_results else 0.5
                all_results[result.chunk_id] = RetrievalResult(
                    chunk_id=result.chunk_id,
                    doc_id=result.doc_id,
                    code=result.code,
                    division=result.division,
                    edition=result.edition,
                    clause_id=result.clause_id,
                    pdf_page=result.pdf_page,
                    type=result.type,
                    text=result.text,
                    score=normalized_score * self.config.keyword_weight
                )
        
        # Add embedding results
        for i, result in enumerate(embedding_results):
            if result.chunk_id not in all_results:
                all_results[result.chunk_id] = result
            else:
                # Combine scores
                existing = all_results[result.chunk_id]
                combined_score = (existing.score + 
                                 result.score * self.config.embedding_weight)
                all_results[result.chunk_id] = RetrievalResult(
                    chunk_id=existing.chunk_id,
                    doc_id=existing.doc_id,
                    code=existing.code,
                    division=existing.division,
                    edition=existing.edition,
                    clause_id=existing.clause_id,
                    pdf_page=existing.pdf_page,
                    type=existing.type,
                    text=existing.text,
                    score=combined_score
                )
        
        # Sort by combined score
        sorted_results = sorted(all_results.values(), key=lambda r: r.score, reverse=True)
        
        # Filter by minimum score
        filtered_results = [r for r in sorted_results if r.score >= self.config.min_score]
        
        return filtered_results
    
    def answer_question(self, question: str, results: List[RetrievalResult]) -> str:
        """
        Generate a grounded answer to a question.
        
        Args:
            question: The question to answer
            results: Retrieved results to use as context
            
        Returns:
            Generated answer text
        """
        if not results:
            return "not found"
        
        # Build context from results
        context = self.build_context(results)
        
        # Generate answer using the chat model
        if self.lm_studio_available:
            try:
                return self.generate_answer(question, context)
            except Exception as e:
                self.logger.warning(f"Failed to generate answer: {str(e)}")
        
        # Fallback: return formatted excerpts
        return self.format_excerpts(results)
    
    def build_context(self, results: List[RetrievalResult]) -> str:
        """
        Build context string from retrieval results.
        
        Args:
            results: List of retrieval results
            
        Returns:
            Formatted context string
        """
        context_parts = []
        
        for i, result in enumerate(results, 1):
            context_parts.append(f"[{i}] {result.code} {result.edition}, {result.division}")
            context_parts.append(f"    Clause: {result.clause_id}")
            context_parts.append(f"    Page: {result.pdf_page}")
            context_parts.append(f"    Type: {result.type}")
            context_parts.append(f"    Text: {result.text}")
            context_parts.append("")
        
        return "\n".join(context_parts)
    
    def generate_answer(self, question: str, context: str) -> str:
        """
        Generate an answer using the chat model.
        
        Args:
            question: The question
            context: Context from retrieval
            
        Returns:
            Generated answer
        """
        try:
            import requests
            import json
            
            # Prepare messages
            messages = [
                {
                    "role": "system",
                    "content": self.SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nContext:\n{context}"
                }
            ]
            
            # Prepare request
            url = f"{self.config.api_url}/chat/completions"
            payload = {
                "model": self.config.chat_model,
                "messages": messages,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            # Send request
            response = requests.post(url, json=payload, headers=headers, 
                                    timeout=self.config.timeout_seconds)
            
            if response.status_code == 200:
                data = response.json()
                answer = data['choices'][0]['message']['content']
                return answer
            else:
                self.logger.warning(f"Chat request failed: {response.status_code}")
                return f"Error: Failed to generate answer (HTTP {response.status_code})"
                
        except Exception as e:
            self.logger.warning(f"Failed to generate answer: {str(e)}")
            return f"Error: Failed to generate answer: {str(e)}"
    
    def format_excerpts(self, results: List[RetrievalResult]) -> str:
        """
        Format retrieval results as excerpts.
        
        Args:
            results: List of retrieval results
            
        Returns:
            Formatted excerpts string
        """
        parts = []
        
        for i, result in enumerate(results, 1):
            parts.append(f"[{i}] {result.code} {result.edition}, {result.clause_id}, PDF p.{result.pdf_page}")
            parts.append(f"    {result.text}")
            parts.append("")
        
        return "\n".join(parts)
    
    def citecheck(self, answer: str, results: List[RetrievalResult]) -> Tuple[str, List[Citation]]:
        """
        Check citations in an answer against retrieved excerpts.
        
        Args:
            answer: The answer text
            results: Retrieved results
            
        Returns:
            Tuple of (answer with warnings, list of unverified citations)
        """
        # Extract citations from answer
        citations = parse_citations_from_text(answer)
        
        # Get all valid citations from results
        valid_citations = set()
        for result in results:
            citation = Citation(
                code=result.code,
                edition=result.edition,
                clause=result.clause_id,
                pdf_page=result.pdf_page
            )
            valid_citations.add(citation.to_string())
        
        # Check each citation
        unverified = []
        for citation in citations:
            if citation.to_string() not in valid_citations:
                unverified.append(citation)
        
        # Add warnings to answer
        if unverified:
            warning = "\n\n**UNVERIFIED CITATIONS:**\n"
            for citation in unverified:
                warning += f"- {citation.to_string()}\n"
            answer = answer + warning
        
        return answer, unverified
    
    def find_materials(self, grade: str) -> List[Dict[str, Any]]:
        """
        Find materials for a given grade.
        
        Args:
            grade: Material grade (e.g., "304L")
            
        Returns:
            List of material specifications
        """
        # Search for materials with this grade
        query = f"{grade} OR {grade.lower()}"
        
        # Filter for materials documents
        filters = {
            'division': 'II-A',
        }
        
        results = self.search(query, filters)
        
        materials = []
        for result in results:
            if result.type in ['text', 'table']:
                material = {
                    'spec': self.extract_spec(result.text),
                    'product_form': self.extract_product_form(result.text),
                    'code': result.code,
                    'division': result.division,
                    'edition': result.edition,
                    'clause_id': result.clause_id,
                    'pdf_page': result.pdf_page,
                    'text': result.text
                }
                materials.append(material)
        
        return materials
    
    def extract_spec(self, text: str) -> str:
        """
        Extract material specification from text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Specification string
        """
        # Look for SA-xxx patterns
        match = re.search(r'SA-\d+', text)
        if match:
            return match.group(0)
        
        # Look for specification patterns
        match = re.search(r'[A-Z]{2,}-\d+', text)
        if match:
            return match.group(0)
        
        return ""
    
    def extract_product_form(self, text: str) -> str:
        """
        Extract product form from text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Product form string
        """
        product_forms = ['plate', 'sheet', 'strip', 'pipe', 'tube', 'forging', 'bar', 'rod']
        
        text_lower = text.lower()
        for form in product_forms:
            if form in text_lower:
                return form
        
        return ""
    
    def evaluate_models(self) -> Dict[str, Dict[str, Any]]:
        """
        Evaluate chat models on test questions.
        
        Returns:
            Dictionary of model evaluation results
        """
        results = {}
        
        # Load evaluation questions
        try:
            import tomllib
            with open(self.config.eval_questions_file, 'rb') as f:
                eval_data = tomllib.load(f)
        except Exception as e:
            self.logger.warning(f"Failed to load evaluation questions: {str(e)}")
            return results
        
        questions = eval_data.get('questions', [])
        
        for model_name in self.config.eval_models:
            model_results = {
                'correct_clauses': 0,
                'total_questions': len(questions),
                'accuracy': 0.0,
                'avg_time': 0.0,
                'details': []
            }
            
            total_time = 0
            
            for question in questions:
                start_time = time.time()
                
                # Search for answer
                search_results = self.search(question.get('question', ''))
                
                # Generate answer
                answer = self.answer_question(question.get('question', ''), search_results)
                
                # Check if correct clause is cited
                expected_clause = question.get('expected_clause', '')
                if expected_clause:
                    citations = parse_citations_from_text(answer)
                    correct = any(c.clause == expected_clause for c in citations)
                    model_results['correct_clauses'] += 1 if correct else 0
                
                elapsed = time.time() - start_time
                total_time += elapsed
                
                model_results['details'].append({
                    'question': question.get('question', ''),
                    'correct': correct,
                    'time': elapsed,
                    'answer': answer[:200] + '...' if len(answer) > 200 else answer
                })
            
            model_results['accuracy'] = (model_results['correct_clauses'] / 
                                        model_results['total_questions']) if model_results['total_questions'] > 0 else 0.0
            model_results['avg_time'] = total_time / len(questions) if questions else 0.0
            
            results[model_name] = model_results
        
        return results


# Test function for the module
if __name__ == '__main__':
    from asme_rag.utils import get_config
    from asme_rag.storage import Storage
    
    config = get_config()
    storage = Storage(config)
    rag_system = RAGSystem(config, storage)
    
    print("Testing RAG system...")
    
    # Test search
    results = rag_system.search("UG-37")
    print(f"Found {len(results)} results for 'UG-37'")
    
    # Test answer generation (will fail without LM Studio)
    if rag_system.lm_studio_available:
        answer = rag_system.answer_question("What are the rules for vacuum design?", results)
        print(f"Answer: {answer[:200]}...")
    else:
        print("LM Studio not available, skipping answer generation test")
    
    # Test materials lookup
    materials = rag_system.find_materials("304L")
    print(f"Found {len(materials)} materials for grade 304L")
    
    print("RAG system tests completed!")
