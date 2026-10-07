"""
ASME RAG Utilities

This module provides utility functions for the ASME RAG system including:
- Configuration loading and validation
- Logging setup
- Common data structures and helpers
- Path resolution
"""

import os
import sys
import json
import logging
import tomllib
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import re
import hashlib
import urllib.parse


# EDIT HERE: Hard maximum depth for cross-reference expansion
MAX_XREF_DEPTH = 1


@dataclass
class Config:
    """Configuration container loaded from config.toml"""
    
    # General settings
    project_name: str = "ASME BPVC RAG + Vacuum Chamber Design Assistant"
    workspace_root: str = "."
    force_utf8: bool = True
    
    # LM Studio settings
    api_url: str = "http://localhost:1234/v1"
    chat_model: str = "gemma-4-26b-a4b"
    embedding_model: str = "nomic-ai/text-embedding-nomic-embed-text-v1.5"
    query_prefix: str = "search_query: "
    chunk_prefix: str = "search_document: "
    temperature: float = 0.1
    max_tokens: int = 4096
    timeout_seconds: int = 120
    
    # Vision settings
    vision_enabled: bool = True
    vision_model: str = "gemma-4-26b-a4b"
    render_dpi: int = 150
    max_image_px: int = 2048
    max_figures_per_run: int = 10
    vision_timeout_s: int = 60
    save_page_images: bool = False
    debug_dir: str = "outputs/debug_images"
    repeat_reads: int = 2
    reading_tolerance_pct: float = 5.0
    vision_resume: bool = True
    
    # PDF parser settings
    strip_patterns: List[str] = field(default_factory=list)
    header_footer_threshold: float = 0.1
    min_text_height: int = 6
    column_gap_threshold: int = 20
    min_column_width: int = 100
    
    # Chunker settings
    target_chunk_size: int = 1024
    min_chunk_size: int = 256
    max_chunk_size: int = 4096
    chunk_overlap: int = 256
    clause_patterns: List[str] = field(default_factory=list)
    table_patterns: List[str] = field(default_factory=list)
    figure_patterns: List[str] = field(default_factory=list)
    xref_patterns: List[str] = field(default_factory=list)
    
    # Documents registry
    documents: List[Dict[str, Any]] = field(default_factory=list)
    
    # Storage settings
    database_path: str = "data/asme_rag.db"
    fts5_tokenize: str = "unicode61 remove_diacritics 2"
    
    # Retrieval settings
    top_k: int = 10
    similarity_threshold: float = 0.7
    keyword_weight: float = 0.4
    embedding_weight: float = 0.6
    min_score: float = 0.5
    
    # Embedding settings
    embedding_dim: int = 768
    batch_size: int = 32
    
    # Cross-reference settings
    xref_max_depth: int = 1
    xref_max_clauses: int = 40
    xref_ask_when_larger_than: int = 40
    xref_include_footnotes: bool = True
    xref_show_unexpanded: bool = True
    xref_write_pack_file: bool = True
    xref_prompt_to_expand: bool = True
    
    # Links settings
    pdf_page_links: bool = True
    pdf_base_dir: str = "data/pdfs"
    anchor_style: str = "#page={n}"
    
    # Serve settings
    serve_host: str = "127.0.0.1"
    serve_port: int = 8765
    
    # Output settings
    open_in_vscode: bool = True
    chat_history_max: int = 3
    
    # Chamber settings
    default_code: str = "ASME VIII-1"
    default_edition: int = 2025
    structural_credit: str = "none"
    fea_nozzle_threshold: int = 5
    
    # Evaluation settings
    eval_models: List[str] = field(default_factory=list)
    eval_questions_file: str = "tests/eval_questions.toml"
    
    # Logging settings
    log_level: str = "INFO"
    log_file: str = "logs/asme_rag.log"
    console_log: bool = True


class ConfigError(Exception):
    """Configuration error exception"""
    pass


class ConfigNotFoundError(ConfigError):
    """Configuration file not found"""
    pass


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load configuration from config.toml file.
    
    Args:
        config_path: Path to config.toml. If None, searches in workspace root.
    
    Returns:
        Config object with all settings.
    
    Raises:
        ConfigNotFoundError: If config file cannot be found.
        ConfigError: If config file is invalid.
    """
    # Determine config file path
    if config_path is None:
        # Search from current directory up to workspace root
        search_paths = [
            os.path.join(os.getcwd(), "config.toml"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.toml"),
            "config.toml"
        ]
        
        for path in search_paths:
            if os.path.exists(path):
                config_path = path
                break
        else:
            raise ConfigNotFoundError(
                f"config.toml not found in: {', '.join(search_paths)}"
            )
    
    # Ensure path exists
    if not os.path.exists(config_path):
        raise ConfigNotFoundError(f"config.toml not found at: {config_path}")
    
    # Load TOML
    try:
        with open(config_path, 'rb') as f:
            config_data = tomllib.load(f)
    except Exception as e:
        raise ConfigError(f"Failed to load config.toml: {str(e)}")
    
    # Convert to Config object
    config = Config()
    
    # Map configuration sections
    if 'general' in config_data:
        general = config_data['general']
        config.project_name = general.get('project_name', config.project_name)
        config.workspace_root = general.get('workspace_root', config.workspace_root)
        config.force_utf8 = general.get('force_utf8', config.force_utf8)
    
    if 'lm_studio' in config_data:
        lm = config_data['lm_studio']
        config.api_url = lm.get('api_url', config.api_url)
        config.chat_model = lm.get('chat_model', config.chat_model)
        config.embedding_model = lm.get('embedding_model', config.embedding_model)
        config.query_prefix = lm.get('query_prefix', config.query_prefix)
        config.chunk_prefix = lm.get('chunk_prefix', config.chunk_prefix)
        config.temperature = lm.get('temperature', config.temperature)
        config.max_tokens = lm.get('max_tokens', config.max_tokens)
        config.timeout_seconds = lm.get('timeout_seconds', config.timeout_seconds)
    
    if 'vision' in config_data:
        vision = config_data['vision']
        config.vision_enabled = vision.get('enabled', config.vision_enabled)
        config.vision_model = vision.get('model', config.vision_model)
        config.render_dpi = vision.get('render_dpi', config.render_dpi)
        config.max_image_px = vision.get('max_image_px', config.max_image_px)
        config.max_figures_per_run = vision.get('max_figures_per_run', config.max_figures_per_run)
        config.vision_timeout_s = vision.get('timeout_s', config.vision_timeout_s)
        config.save_page_images = vision.get('save_page_images', config.save_page_images)
        config.debug_dir = vision.get('debug_dir', config.debug_dir)
        config.repeat_reads = vision.get('repeat_reads', config.repeat_reads)
        config.reading_tolerance_pct = vision.get('reading_tolerance_pct', config.reading_tolerance_pct)
        config.vision_resume = vision.get('resume', config.vision_resume)
    
    if 'pdf_parser' in config_data:
        parser = config_data['pdf_parser']
        config.strip_patterns = parser.get('strip_patterns', config.strip_patterns)
        config.header_footer_threshold = parser.get('header_footer_threshold', config.header_footer_threshold)
        config.min_text_height = parser.get('min_text_height', config.min_text_height)
        config.column_gap_threshold = parser.get('column_gap_threshold', config.column_gap_threshold)
        config.min_column_width = parser.get('min_column_width', config.min_column_width)
    
    if 'chunker' in config_data:
        chunker = config_data['chunker']
        config.target_chunk_size = chunker.get('target_chunk_size', config.target_chunk_size)
        config.min_chunk_size = chunker.get('min_chunk_size', config.min_chunk_size)
        config.max_chunk_size = chunker.get('max_chunk_size', config.max_chunk_size)
        config.chunk_overlap = chunker.get('chunk_overlap', config.chunk_overlap)
        config.clause_patterns = chunker.get('clause_patterns', config.clause_patterns)
        config.table_patterns = chunker.get('table_patterns', config.table_patterns)
        config.figure_patterns = chunker.get('figure_patterns', config.figure_patterns)
        config.xref_patterns = chunker.get('xref_patterns', config.xref_patterns)
    
    if 'documents' in config_data:
        config.documents = config_data['documents']
    
    if 'storage' in config_data:
        storage = config_data['storage']
        config.database_path = storage.get('database_path', config.database_path)
        config.fts5_tokenize = storage.get('fts5_tokenize', config.fts5_tokenize)
    
    if 'retrieval' in config_data:
        retrieval = config_data['retrieval']
        config.top_k = retrieval.get('top_k', config.top_k)
        config.similarity_threshold = retrieval.get('similarity_threshold', config.similarity_threshold)
        config.keyword_weight = retrieval.get('keyword_weight', config.keyword_weight)
        config.embedding_weight = retrieval.get('embedding_weight', config.embedding_weight)
        config.min_score = retrieval.get('min_score', config.min_score)
    
    if 'embedding' in config_data:
        embedding = config_data['embedding']
        config.embedding_dim = embedding.get('embedding_dim', config.embedding_dim)
        config.batch_size = embedding.get('batch_size', config.batch_size)
    
    if 'xref' in config_data:
        xref = config_data['xref']
        config.xref_max_depth = xref.get('max_depth', config.xref_max_depth)
        config.xref_max_clauses = xref.get('max_clauses', config.xref_max_clauses)
        config.xref_ask_when_larger_than = xref.get('ask_when_larger_than', config.xref_ask_when_larger_than)
        config.xref_include_footnotes = xref.get('include_footnotes', config.xref_include_footnotes)
        config.xref_show_unexpanded = xref.get('show_unexpanded', config.xref_show_unexpanded)
        config.xref_write_pack_file = xref.get('write_pack_file', config.xref_write_pack_file)
        config.xref_prompt_to_expand = xref.get('prompt_to_expand', config.xref_prompt_to_expand)
    
    if 'links' in config_data:
        links = config_data['links']
        config.pdf_page_links = links.get('pdf_page_links', config.pdf_page_links)
        config.pdf_base_dir = links.get('pdf_base_dir', config.pdf_base_dir)
        config.anchor_style = links.get('anchor_style', config.anchor_style)
    
    if 'serve' in config_data:
        serve = config_data['serve']
        config.serve_host = serve.get('host', config.serve_host)
        config.serve_port = serve.get('port', config.serve_port)
    
    if 'output' in config_data:
        output = config_data['output']
        config.open_in_vscode = output.get('open_in_vscode', config.open_in_vscode)
        config.chat_history_max = output.get('chat_history_max', config.chat_history_max)
    
    if 'chamber' in config_data:
        chamber = config_data['chamber']
        config.default_code = chamber.get('default_code', config.default_code)
        config.default_edition = chamber.get('default_edition', config.default_edition)
        config.structural_credit = chamber.get('structural_credit', config.structural_credit)
        config.fea_nozzle_threshold = chamber.get('fea_nozzle_threshold', config.fea_nozzle_threshold)
    
    if 'eval' in config_data:
        eval_config = config_data['eval']
        config.eval_models = eval_config.get('models', config.eval_models)
        config.eval_questions_file = eval_config.get('eval_questions_file', config.eval_questions_file)
    
    if 'logging' in config_data:
        logging_config = config_data['logging']
        config.log_level = logging_config.get('level', config.log_level)
        config.log_file = logging_config.get('log_file', config.log_file)
        config.console_log = logging_config.get('console_log', config.console_log)
    
    # Validate and resolve paths
    config = _validate_and_resolve_config(config)
    
    return config


def _validate_and_resolve_config(config: Config) -> Config:
    """Validate configuration and resolve relative paths."""
    
    # Get absolute workspace root
    workspace_root = os.path.abspath(config.workspace_root)
    
    # Resolve relative paths
    if not os.path.isabs(config.database_path):
        config.database_path = os.path.join(workspace_root, config.database_path)
    
    if not os.path.isabs(config.debug_dir):
        config.debug_dir = os.path.join(workspace_root, config.debug_dir)
    
    if not os.path.isabs(config.log_file):
        config.log_file = os.path.join(workspace_root, config.log_file)
    
    if not os.path.isabs(config.pdf_base_dir):
        config.pdf_base_dir = os.path.join(workspace_root, config.pdf_base_dir)
    
    if not os.path.isabs(config.eval_questions_file):
        config.eval_questions_file = os.path.join(workspace_root, config.eval_questions_file)
    
    # Ensure directories exist
    os.makedirs(os.path.dirname(config.database_path), exist_ok=True)
    os.makedirs(config.debug_dir, exist_ok=True)
    os.makedirs(os.path.dirname(config.log_file), exist_ok=True)
    
    # Validate document paths
    for doc in config.documents:
        if 'pdf_path' in doc and not os.path.isabs(doc['pdf_path']):
            doc['pdf_path'] = os.path.join(workspace_root, doc['pdf_path'])
    
    return config


def setup_logging(config: Config) -> logging.Logger:
    """
    Set up logging based on configuration.
    
    Args:
        config: Configuration object
    
    Returns:
        Configured logger
    """
    # Create logs directory
    log_dir = os.path.dirname(config.log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    
    # Convert log level string to logging constant
    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    level = level_map.get(config.log_level.upper(), logging.INFO)
    
    # Create logger
    logger = logging.getLogger('asme_rag')
    logger.setLevel(level)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # File handler
    file_handler = logging.FileHandler(config.log_file, encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console handler
    if config.console_log:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger


def force_utf8_console():
    """Force UTF-8 console output on Windows."""
    if sys.platform == 'win32':
        import ctypes
        kernel32 = ctypes.windll.kernel32
        
        # Set console output to UTF-8
        kernel32.SetConsoleOutputCP(65001)
        
        # For Python 3.7+
        if hasattr(sys, 'stdout'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys, 'stderr'):
            sys.stderr.reconfigure(encoding='utf-8')


@dataclass
class ChunkMetadata:
    """Metadata for a text chunk."""
    
    # Document identification
    doc_id: str
    code: str
    division: str
    edition: int
    part_or_subsection: str = ""
    clause_id: str = ""
    
    # Location
    pdf_page: int = 0
    
    # Content type
    type: str = "text"  # text / table / figure_caption / figure_description / equation / footnote / note
    
    # Processing flags
    model_generated: bool = False
    verified: bool = False
    status: str = "mandatory"  # mandatory / non-mandatory / supplementary
    
    # Structure
    heading_path: str = ""
    bold_flags: str = ""
    
    # Text content
    text: str = ""
    
    # Hash for deduplication
    content_hash: str = ""
    
    def __post_init__(self):
        if not self.content_hash and self.text:
            self.content_hash = self.compute_hash()
    
    def compute_hash(self) -> str:
        """Compute hash of chunk content."""
        content = f"{self.doc_id}:{self.clause_id}:{self.text}".encode('utf-8')
        return hashlib.sha256(content).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'doc_id': self.doc_id,
            'code': self.code,
            'division': self.division,
            'edition': self.edition,
            'part_or_subsection': self.part_or_subsection,
            'clause_id': self.clause_id,
            'pdf_page': self.pdf_page,
            'type': self.type,
            'model_generated': self.model_generated,
            'verified': self.verified,
            'status': self.status,
            'heading_path': self.heading_path,
            'bold_flags': self.bold_flags,
            'text': self.text,
            'content_hash': self.content_hash
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChunkMetadata':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class RetrievalResult:
    """Result from a retrieval query."""
    
    chunk_id: str
    doc_id: str
    code: str
    division: str
    edition: int
    clause_id: str
    pdf_page: int
    type: str
    text: str
    score: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'chunk_id': self.chunk_id,
            'doc_id': self.doc_id,
            'code': self.code,
            'division': self.division,
            'edition': self.edition,
            'clause_id': self.clause_id,
            'pdf_page': self.pdf_page,
            'type': self.type,
            'text': self.text,
            'score': self.score
        }


@dataclass
class Citation:
    """A citation reference."""
    
    code: str
    edition: int
    clause: str
    pdf_page: int
    
    def to_string(self) -> str:
        """Format citation as string."""
        return f"[{self.code}, {self.edition}, {self.clause}, PDF p.{self.pdf_page}]"
    
    def to_markdown_link(self, pdf_base_dir: str, anchor_style: str = "#page={n}") -> str:
        """Convert citation to Markdown link."""
        # Find the PDF file for this citation
        # This is a simplified version - in practice, we'd need to map code/edition to PDF file
        pdf_file = f"{self.code.replace(' ', '_')}_{self.edition}.pdf"
        pdf_path = os.path.join(pdf_base_dir, pdf_file)
        
        # URL encode the path
        encoded_path = urllib.parse.quote(pdf_path.replace('\\', '/'))
        
        # Create file URL
        file_url = f"file:///{encoded_path}"
        
        # Create anchor
        anchor = anchor_style.format(n=self.pdf_page)
        
        # Create link
        link_text = self.to_string()
        return f"[{link_text}]({file_url}{anchor})"


def parse_citation_from_text(text: str) -> Optional[Citation]:
    """
    Parse a citation from text format.
    
    Expected format: [code, edition, clause, PDF p.N]
    """
    # Pattern: [code, edition, clause, PDF p.N]
    pattern = r'\[([^,\]]+),\s*(\d{4}),\s*([^,\]]+),\s*PDF\s+p\.(\d+)\]'
    match = re.search(pattern, text)
    
    if match:
        code = match.group(1).strip()
        edition = int(match.group(2))
        clause = match.group(3).strip()
        pdf_page = int(match.group(4))
        
        return Citation(code, edition, clause, pdf_page)
    
    return None


def parse_citations_from_text(text: str) -> List[Citation]:
    """Parse all citations from text."""
    citations = []
    pattern = r'\[([^,\]]+),\s*(\d{4}),\s*([^,\]]+),\s*PDF\s+p\.(\d+)\]'
    
    for match in re.finditer(pattern, text):
        code = match.group(1).strip()
        edition = int(match.group(2))
        clause = match.group(3).strip()
        pdf_page = int(match.group(4))
        
        citations.append(Citation(code, edition, clause, pdf_page))
    
    return citations


def resolve_workspace_path(path: str, workspace_root: str = None) -> str:
    """
    Resolve a path relative to the workspace root.
    
    Args:
        path: Path to resolve
        workspace_root: Workspace root directory
    
    Returns:
        Absolute path
    """
    if workspace_root is None:
        workspace_root = os.getcwd()
    
    if os.path.isabs(path):
        return path
    
    return os.path.join(workspace_root, path)


def get_workspace_root() -> str:
    """Get the workspace root directory."""
    # Try to find .vscode directory or config.toml
    current_dir = os.getcwd()
    
    while True:
        if os.path.exists(os.path.join(current_dir, 'config.toml')):
            return current_dir
        
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            break
        current_dir = parent_dir
    
    return os.getcwd()


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reset_config():
    """Reset the global configuration instance."""
    global _config
    _config = None


# Initialize UTF-8 console
if sys.platform == 'win32':
    force_utf8_console()
