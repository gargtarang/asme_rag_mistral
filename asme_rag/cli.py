"""
ASME RAG Command-Line Interface

This module provides the command-line interface for the ASME RAG system.

Usage:
    python -m asme_rag <command> [args]

Commands:
    check - Verify system configuration and connectivity
    ingest - Parse and chunk all registered PDFs
    embed - Create embeddings for all chunks
    search - Perform a retrieval search
    ask - Ask a question and get a grounded answer
    chat - Start an interactive chat session
    refs - Expand cross-references for a clause
    rulemap - Generate a rule map for a topic
    materials - List materials for a grade
    describe-figures - Describe figures in PDFs
    figure-read - Read values from figures
    table-from-image - Transcribe tables from images
    vision-test - Test vision capabilities
    eval - Evaluate chat models
    serve - Start local web server (optional, phase 10)
"""

import sys
import os
import argparse
import json
import time
from typing import List, Optional, Dict, Any
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asme_rag.utils import get_config, setup_logging, Config, force_utf8_console
from asme_rag.pdf_parser import PDFParser
from asme_rag.chunker import Chunker
from asme_rag.storage import Storage
from asme_rag.rag import RAGSystem
from asme_rag.vision import VisionSystem
from asme_rag.xref import CrossReferenceExpander


class CLI:
    """Command-line interface for ASME RAG."""
    
    def __init__(self):
        self.config = get_config()
        self.logger = setup_logging(self.config)
        self.storage = None
        self.rag_system = None
        self.vision_system = None
        self.xref_expander = None
        
    def initialize_systems(self):
        """Initialize all subsystems."""
        try:
            self.storage = Storage(self.config)
            self.rag_system = RAGSystem(self.config, self.storage)
            self.vision_system = VisionSystem(self.config, self.storage)
            self.xref_expander = CrossReferenceExpander(self.config, self.storage)
        except Exception as e:
            self.logger.error(f"Failed to initialize systems: {str(e)}")
            raise
    
    def run(self, args: List[str]):
        """Run the CLI with the given arguments."""
        if not args:
            self.print_help()
            return
        
        command = args[0]
        command_args = args[1:]
        
        try:
            if command == 'check':
                self.cmd_check(command_args)
            elif command == 'ingest':
                self.cmd_ingest(command_args)
            elif command == 'embed':
                self.cmd_embed(command_args)
            elif command == 'search':
                self.cmd_search(command_args)
            elif command == 'ask':
                self.cmd_ask(command_args)
            elif command == 'chat':
                self.cmd_chat(command_args)
            elif command == 'refs':
                self.cmd_refs(command_args)
            elif command == 'rulemap':
                self.cmd_rulemap(command_args)
            elif command == 'materials':
                self.cmd_materials(command_args)
            elif command == 'describe-figures':
                self.cmd_describe_figures(command_args)
            elif command == 'figure-read':
                self.cmd_figure_read(command_args)
            elif command == 'table-from-image':
                self.cmd_table_from_image(command_args)
            elif command == 'vision-test':
                self.cmd_vision_test(command_args)
            elif command == 'eval':
                self.cmd_eval(command_args)
            elif command == 'serve':
                self.cmd_serve(command_args)
            elif command == 'page':
                self.cmd_page(command_args)
            elif command == 'clause':
                self.cmd_clause(command_args)
            elif command == 'inspect':
                self.cmd_inspect(command_args)
            else:
                self.logger.error(f"Unknown command: {command}")
                self.print_help()
        except Exception as e:
            self.logger.error(f"Command '{command}' failed: {str(e)}")
            if self.config.console_log:
                print(f"Error: {str(e)}", file=sys.stderr)
            sys.exit(1)
    
    def print_help(self):
        """Print help message."""
        help_text = """
ASME RAG + Chamber Design Assistant

Usage:
    python -m asme_rag <command> [args]

Commands:
    check                           Verify system configuration and connectivity
    ingest [--no-embed]             Parse and chunk all registered PDFs
    embed [--redo]                  Create embeddings for all chunks
    search <query>                 Perform a retrieval search
    ask <question>                 Ask a question and get a grounded answer
    chat                           Start an interactive chat session
    refs <clause> [--doc ID]       Expand cross-references for a clause
    rulemap <topic>                Generate a rule map for a topic
    materials <grade>              List materials for a grade
    describe-figures [--doc ID] [--page N]
                                   Describe figures in PDFs
    figure-read                    Read values from figures (interactive)
    table-from-image               Transcribe tables from images (interactive)
    vision-test                    Test vision capabilities
    eval                           Evaluate chat models on test questions
    serve                          Start local web server (optional)
    page <N>                       Show reading order for PDF page N
    clause <ID>                    Print a clause with its metadata
    inspect [--part X]             List structure and chunk counts

Examples:
    python -m asme_rag check
    python -m asme_rag ingest
    python -m asme_rag embed
    python -m asme_rag ask "What are the rules for vacuum design?"
    python -m asme_rag search "UG-37"
    python -m asme_rag refs "UG-37"
    python -m asme_rag materials "304L"

Configuration:
    Edit config.toml to customize settings.
"""
        print(help_text)
    
    def cmd_check(self, args: List[str]):
        """Check system configuration and connectivity."""
        print("Checking ASME RAG system...")
        
        # Check Python version
        print(f"Python version: {sys.version}")
        
        # Check configuration
        print(f"Configuration file: {self.config.__class__.__name__} loaded")
        print(f"Workspace root: {self.config.workspace_root}")
        print(f"Database path: {self.config.database_path}")
        
        # Check LM Studio connectivity
        self.check_lm_studio()
        
        # Check PDFs
        self.check_pdfs()
        
        # Check database
        self.check_database()
        
        # Check dependencies
        self.check_dependencies()
        
        print("\nSystem check completed.")
    
    def check_lm_studio(self):
        """Check LM Studio connectivity."""
        print(f"\nChecking LM Studio at {self.config.api_url}...")
        
        try:
            # Try to import requests
            import requests
            
            # Try a simple GET request to check if server is running
            try:
                response = requests.get(
                    f"{self.config.api_url}/models",
                    timeout=self.config.timeout_seconds
                )
                if response.status_code == 200:
                    models = response.json().get('data', [])
                    model_names = [m.get('id', 'unknown') for m in models]
                    print(f"  LM Studio is running")
                    print(f"  Available models: {', '.join(model_names)}")
                    
                    # Check if our models are available
                    if self.config.chat_model in model_names:
                        print(f"  Chat model '{self.config.chat_model}' is available")
                    else:
                        print(f"  WARNING: Chat model '{self.config.chat_model}' not found")
                    
                    if self.config.embedding_model in model_names:
                        print(f"  Embedding model '{self.config.embedding_model}' is available")
                    else:
                        print(f"  WARNING: Embedding model '{self.config.embedding_model}' not found")
                else:
                    print(f"  WARNING: LM Studio returned status {response.status_code}")
            except requests.exceptions.ConnectionError:
                print(f"  WARNING: Cannot connect to LM Studio at {self.config.api_url}")
                print(f"  This is expected if LM Studio is not running.")
                print(f"  The fake server can be used for testing: python -m tests.fake_lm_server")
            except Exception as e:
                print(f"  WARNING: Error connecting to LM Studio: {str(e)}")
                
        except ImportError:
            print("  WARNING: 'requests' package not installed")
    
    def check_pdfs(self):
        """Check that PDF files are present."""
        print(f"\nChecking PDF files...")
        
        pdf_count = 0
        missing_pdfs = []
        
        for doc in self.config.documents:
            pdf_path = doc.get('pdf_path', '')
            if pdf_path and os.path.exists(pdf_path):
                pdf_count += 1
                print(f"  FOUND: {doc.get('id', 'unknown')} at {pdf_path}")
            elif pdf_path:
                missing_pdfs.append(f"{doc.get('id', 'unknown')} ({pdf_path})")
        
        if pdf_count > 0:
            print(f"  {pdf_count} PDF files found")
        
        if missing_pdfs:
            print(f"  WARNING: Missing PDFs: {', '.join(missing_pdfs)}")
    
    def check_database(self):
        """Check database state."""
        print(f"\nChecking database...")
        
        try:
            self.initialize_systems()
            
            if self.storage:
                stats = self.storage.get_statistics()
                print(f"  Database exists: {os.path.exists(self.config.database_path)}")
                print(f"  Chunks stored: {stats['chunk_count']}")
                print(f"  Documents indexed: {stats['doc_count']}")
                print(f"  Embeddings stored: {stats['embedding_count']}")
        except Exception as e:
            print(f"  WARNING: Database check failed: {str(e)}")
    
    def check_dependencies(self):
        """Check that required Python packages are installed."""
        print(f"\nChecking dependencies...")
        
        required_packages = [
            'PyMuPDF',
            'requests',
            'httpx',
            'numpy',
            'tomli',
            'tomli_w',
            'Pillow'
        ]
        
        missing = []
        for package in required_packages:
            try:
                __import__(package if package != 'tomli_w' else 'tomli_w')
                print(f"  OK: {package}")
            except ImportError:
                missing.append(package)
                print(f"  MISSING: {package}")
        
        if missing:
            print(f"\n  Install missing packages with: pip install {' '.join(missing)}")
    
    def cmd_ingest(self, args: List[str]):
        """Ingest and chunk all registered PDFs."""
        no_embed = '--no-embed' in args
        
        print("Starting PDF ingestion...")
        self.initialize_systems()
        
        parser = PDFParser(self.config)
        chunker = Chunker(self.config)
        
        total_chunks = 0
        start_time = time.time()
        
        for doc in self.config.documents:
            doc_id = doc.get('id', 'unknown')
            pdf_path = doc.get('pdf_path', '')
            
            if not os.path.exists(pdf_path):
                print(f"  SKIPPING: {doc_id} (PDF not found)")
                continue
            
            print(f"  Processing: {doc_id}")
            
            try:
                # Parse PDF
                parsed_data = parser.parse(pdf_path)
                print(f"    Pages parsed: {len(parsed_data.get('pages', []))}")
                
                # Chunk data
                chunks = chunker.chunk(parsed_data, doc)
                print(f"    Chunks created: {len(chunks)}")
                
                # Store chunks
                if self.storage:
                    stored_count = self.storage.store_chunks(chunks)
                    print(f"    Chunks stored: {stored_count}")
                
                total_chunks += len(chunks)
                
            except Exception as e:
                print(f"    ERROR: {str(e)}")
        
        elapsed = time.time() - start_time
        print(f"\nIngestion completed: {total_chunks} chunks in {elapsed:.2f}s")
        
        # Create embeddings if not --no-embed
        if not no_embed:
            print("\nCreating embeddings...")
            self.cmd_embed([])
    
    def cmd_embed(self, args: List[str]):
        """Create embeddings for all chunks."""
        redo = '--redo' in args
        
        print("Creating embeddings...")
        self.initialize_systems()
        
        if not self.rag_system:
            print("Error: RAG system not initialized")
            return
        
        start_time = time.time()
        
        try:
            count = self.rag_system.create_embeddings(redo=redo)
            elapsed = time.time() - start_time
            print(f"Embeddings created: {count} in {elapsed:.2f}s")
        except Exception as e:
            print(f"Error creating embeddings: {str(e)}")
    
    def cmd_search(self, args: List[str]):
        """Perform a retrieval search."""
        if not args:
            print("Usage: python -m asme_rag search <query>")
            return
        
        query = ' '.join(args)
        print(f"Searching: {query}")
        
        self.initialize_systems()
        
        if not self.rag_system:
            print("Error: RAG system not initialized")
            return
        
        try:
            results = self.rag_system.search(query)
            
            print(f"\nFound {len(results)} results:")
            for i, result in enumerate(results, 1):
                print(f"\n{i}. {result.clause_id} (p.{result.pdf_page}) - Score: {result.score:.3f}")
                print(f"   {result.code} {result.edition}, {result.division}")
                print(f"   {result.text[:200]}...")
        except Exception as e:
            print(f"Error searching: {str(e)}")
    
    def cmd_ask(self, args: List[str]):
        """Ask a question and get a grounded answer."""
        if not args:
            print("Usage: python -m asme_rag ask <question>")
            return
        
        question = ' '.join(args)
        print(f"Question: {question}")
        
        self.initialize_systems()
        
        if not self.rag_system:
            print("Error: RAG system not initialized")
            return
        
        try:
            # Search for relevant chunks
            results = self.rag_system.search(question)
            
            print(f"\nRetrieved {len(results)} excerpts:")
            for i, result in enumerate(results, 1):
                print(f"\n[{i}] {result.clause_id} (p.{result.pdf_page})")
                print(f"   {result.text[:300]}...")
            
            # Generate answer
            answer = self.rag_system.answer_question(question, results)
            
            print(f"\n{answer}")
            
            # Save to file
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
            topic = question[:50].replace(' ', '_').replace('?', '')
            filename = f"outputs/chat/{timestamp}_{topic}.md"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"# Question: {question}\n\n")
                f.write("## Retrieved excerpts\n\n")
                for i, result in enumerate(results, 1):
                    f.write(f"### Excerpt {i}\n")
                    f.write(f"- **Clause**: {result.clause_id}\n")
                    f.write(f"- **Page**: {result.pdf_page}\n")
                    f.write(f"- **Source**: {result.code} {result.edition}, {result.division}\n")
                    f.write(f"- **Text**: {result.text}\n\n")
                
                f.write("## Answer\n\n")
                f.write(f"{answer}\n")
            
            print(f"\nAnswer saved to: {filename}")
            
            # Open in VS Code if configured
            if self.config.open_in_vscode:
                import subprocess
                subprocess.run(['code', '-r', filename], shell=True)
                
        except Exception as e:
            print(f"Error answering question: {str(e)}")
    
    def cmd_chat(self, args: List[str]):
        """Start an interactive chat session."""
        print("Starting interactive chat session...")
        print("Type 'quit' or 'exit' to end the session.")
        print("Type 'clear' to clear the chat history.")
        
        self.initialize_systems()
        
        if not self.rag_system:
            print("Error: RAG system not initialized")
            return
        
        # Chat history
        history = []
        
        try:
            while True:
                try:
                    question = input("\nYou: ")
                except (EOFError, KeyboardInterrupt):
                    print("\nGoodbye!")
                    break
                
                if question.lower() in ['quit', 'exit']:
                    print("Goodbye!")
                    break
                
                if question.lower() == 'clear':
                    history.clear()
                    print("Chat history cleared.")
                    continue
                
                if not question.strip():
                    continue
                
                # Add to history
                history.append({'role': 'user', 'content': question})
                
                # Search and answer
                results = self.rag_system.search(question)
                answer = self.rag_system.answer_question(question, results)
                
                # Add answer to history
                history.append({'role': 'assistant', 'content': answer})
                
                # Keep only last N items
                if len(history) > self.config.chat_history_max * 2:
                    history = history[-self.config.chat_history_max * 2:]
                
                print(f"\nAssistant: {answer}")
                
                # Save to file
                timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
                filename = f"outputs/chat/{timestamp}_chat.md"
                
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"# Chat Session\n\n")
                    f.write(f"**Started**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    
                    for i, msg in enumerate(history):
                        role = msg['role'].capitalize()
                        f.write(f"## {role}\n\n")
                        f.write(f"{msg['content']}\n\n")
                
                print(f"(Saved to: {filename})")
                
        except Exception as e:
            print(f"Chat error: {str(e)}")
    
    def cmd_refs(self, args: List[str]):
        """Expand cross-references for a clause."""
        if not args:
            print("Usage: python -m asme_rag refs <clause> [--doc ID]")
            return
        
        clause_id = args[0]
        doc_id = None
        
        if len(args) > 1 and args[1] == '--doc':
            if len(args) > 2:
                doc_id = args[2]
            else:
                print("Error: --doc requires a document ID")
                return
        
        print(f"Expanding cross-references for: {clause_id}")
        if doc_id:
            print(f"Document: {doc_id}")
        
        self.initialize_systems()
        
        if not self.xref_expander:
            print("Error: Cross-reference system not initialized")
            return
        
        try:
            results = self.xref_expander.expand(clause_id, doc_id=doc_id)
            
            print(f"\nCross-reference expansion for {clause_id}:")
            print("=" * 60)
            
            for level, items in results.items():
                print(f"\n{level}:")
                for item in items:
                    print(f"  - {item}")
            
        except Exception as e:
            print(f"Error expanding cross-references: {str(e)}")
    
    def cmd_rulemap(self, args: List[str]):
        """Generate a rule map for a topic."""
        if not args:
            print("Usage: python -m asme_rag rulemap <topic>")
            return
        
        topic = ' '.join(args)
        print(f"Generating rule map for: {topic}")
        
        self.initialize_systems()
        
        if not self.xref_expander:
            print("Error: Cross-reference system not initialized")
            return
        
        try:
            rulemap = self.xref_expander.generate_rulemap(topic)
            
            print(f"\nRule Map: {topic}")
            print("=" * 60)
            
            for section, items in rulemap.items():
                print(f"\n{section}:")
                for item in items:
                    print(f"  - {item}")
            
        except Exception as e:
            print(f"Error generating rule map: {str(e)}")
    
    def cmd_materials(self, args: List[str]):
        """List materials for a grade."""
        if not args:
            print("Usage: python -m asme_rag materials <grade>")
            return
        
        grade = args[0]
        print(f"Searching for materials with grade: {grade}")
        
        self.initialize_systems()
        
        if not self.rag_system:
            print("Error: RAG system not initialized")
            return
        
        try:
            results = self.rag_system.find_materials(grade)
            
            if results:
                print(f"\nFound {len(results)} specifications for grade {grade}:")
                for i, result in enumerate(results, 1):
                    print(f"\n{i}. {result.spec}")
                    print(f"   Product form: {result.product_form}")
                    print(f"   Code: {result.code}")
                    print(f"   Division: {result.division}")
                    print(f"   Edition: {result.edition}")
                    print(f"   Clause: {result.clause_id}")
                    print(f"   Page: {result.pdf_page}")
            else:
                print(f"No materials found for grade {grade}")
                
        except Exception as e:
            print(f"Error searching materials: {str(e)}")
    
    def cmd_describe_figures(self, args: List[str]):
        """Describe figures in PDFs."""
        doc_id = None
        page_num = None
        
        i = 0
        while i < len(args):
            if args[i] == '--doc' and i + 1 < len(args):
                doc_id = args[i + 1]
                i += 2
            elif args[i] == '--page' and i + 1 < len(args):
                page_num = int(args[i + 1])
                i += 2
            else:
                i += 1
        
        print(f"Describing figures...")
        if doc_id:
            print(f"Document: {doc_id}")
        if page_num:
            print(f"Page: {page_num}")
        
        self.initialize_systems()
        
        if not self.vision_system:
            print("Error: Vision system not initialized")
            return
        
        try:
            results = self.vision_system.describe_figures(doc_id=doc_id, page_num=page_num)
            
            print(f"\nDescribed {len(results)} figures:")
            for i, result in enumerate(results, 1):
                print(f"\n{i}. Figure on page {result.page}")
                print(f"   Description: {result.description[:200]}...")
                print(f"   Status: {'VERIFIED' if result.verified else 'UNVERIFIED'}")
                
        except Exception as e:
            print(f"Error describing figures: {str(e)}")
    
    def cmd_figure_read(self, args: List[str]):
        """Read values from figures (interactive)."""
        print("Figure reading mode (interactive)")
        print("This command helps read values from charts and figures.")
        print("It will prompt for book, figure, page, and inputs.")
        
        self.initialize_systems()
        
        if not self.vision_system:
            print("Error: Vision system not initialized")
            return
        
        try:
            # Get user input
            doc_id = input("Document ID (e.g., viii1_2025): ")
            figure_num = input("Figure number: ")
            page_num = int(input("PDF page number: "))
            chart_inputs = input("Chart inputs (comma-separated): ")
            curve = input("Curve/line to use: ")
            value_name = input("Value name to read: ")
            unit = input("Unit: ")
            
            # Read figure
            result = self.vision_system.read_figure(
                doc_id=doc_id,
                figure_num=figure_num,
                page_num=page_num,
                chart_inputs=chart_inputs,
                curve=curve,
                value_name=value_name,
                unit=unit
            )
            
            print(f"\nResult: {result}")
            
        except Exception as e:
            print(f"Error reading figure: {str(e)}")
    
    def cmd_table_from_image(self, args: List[str]):
        """Transcribe tables from images (interactive)."""
        print("Table transcription mode (interactive)")
        print("This command helps transcribe tables from images.")
        
        self.initialize_systems()
        
        if not self.vision_system:
            print("Error: Vision system not initialized")
            return
        
        try:
            doc_id = input("Document ID: ")
            page_num = int(input("PDF page number: "))
            table_num = input("Table number (optional): ")
            
            result = self.vision_system.transcribe_table(
                doc_id=doc_id,
                page_num=page_num,
                table_num=table_num
            )
            
            print(f"\nTranscribed table:\n{result}")
            
        except Exception as e:
            print(f"Error transcribing table: {str(e)}")
    
    def cmd_vision_test(self, args: List[str]):
        """Test vision capabilities."""
        print("Running vision tests...")
        
        self.initialize_systems()
        
        if not self.vision_system:
            print("Error: Vision system not initialized")
            return
        
        try:
            results = self.vision_system.run_tests()
            
            print(f"\nVision test results:")
            for i, result in enumerate(results, 1):
                print(f"\n{i}. {result.test_name}")
                print(f"   Status: {result.status}")
                print(f"   Time: {result.time:.2f}s")
                if result.error:
                    print(f"   Error: {result.error}")
                if result.value:
                    print(f"   Value: {result.value}")
                    
        except Exception as e:
            print(f"Error running vision tests: {str(e)}")
    
    def cmd_eval(self, args: List[str]):
        """Evaluate chat models on test questions."""
        print("Running model evaluation...")
        
        self.initialize_systems()
        
        if not self.rag_system:
            print("Error: RAG system not initialized")
            return
        
        try:
            results = self.rag_system.evaluate_models()
            
            print(f"\nEvaluation results:")
            for model, metrics in results.items():
                print(f"\n{model}:")
                print(f"  Correct clauses: {metrics.get('correct_clauses', 0)}")
                print(f"  Total questions: {metrics.get('total_questions', 0)}")
                print(f"  Accuracy: {metrics.get('accuracy', 0):.2%}")
                print(f"  Avg time: {metrics.get('avg_time', 0):.2f}s")
                
        except Exception as e:
            print(f"Error running evaluation: {str(e)}")
    
    def cmd_serve(self, args: List[str]):
        """Start local web server (optional, phase 10)."""
        print("Local web server (phase 10 - optional)")
        print("This feature is not implemented yet.")
        print("It will be available after phase 9 is completed.")
    
    def cmd_page(self, args: List[str]):
        """Show reading order for a PDF page."""
        if not args:
            print("Usage: python -m asme_rag page <N>")
            return
        
        try:
            page_num = int(args[0])
        except ValueError:
            print("Error: Page number must be an integer")
            return
        
        print(f"Showing reading order for page {page_num}")
        
        self.initialize_systems()
        
        try:
            parser = PDFParser(self.config)
            
            # We need a PDF to parse - use the first available
            for doc in self.config.documents:
                pdf_path = doc.get('pdf_path', '')
                if os.path.exists(pdf_path):
                    parsed_data = parser.parse(pdf_path)
                    
                    if page_num <= len(parsed_data.get('pages', [])):
                        page_data = parsed_data['pages'][page_num - 1]
                        
                        print(f"\nPage {page_num} reading order:")
                        for i, block in enumerate(page_data.get('blocks', []), 1):
                            print(f"\n{i}. Block at ({block.get('x', 0)}, {block.get('y', 0)})")
                            print(f"   Size: {block.get('width', 0)}x{block.get('height', 0)}")
                            print(f"   Type: {block.get('type', 'text')}")
                            text = block.get('text', '')
                            if text:
                                print(f"   Text: {text[:100]}...")
                    else:
                        print(f"Page {page_num} not found in this PDF")
                    break
            else:
                print("No PDF files found to parse")
                
        except Exception as e:
            print(f"Error showing page: {str(e)}")
    
    def cmd_clause(self, args: List[str]):
        """Print a clause with its metadata."""
        if not args:
            print("Usage: python -m asme_rag clause <ID>")
            return
        
        clause_id = args[0]
        print(f"Looking up clause: {clause_id}")
        
        self.initialize_systems()
        
        if not self.storage:
            print("Error: Storage not initialized")
            return
        
        try:
            chunks = self.storage.get_chunks_by_clause(clause_id)
            
            if chunks:
                print(f"\nFound {len(chunks)} chunks for clause {clause_id}:")
                for i, chunk in enumerate(chunks, 1):
                    print(f"\n{i}. Chunk {chunk['chunk_id']}")
                    print(f"   Document: {chunk['doc_id']}")
                    print(f"   Code: {chunk['code']} {chunk['edition']}")
                    print(f"   Division: {chunk['division']}")
                    print(f"   Page: {chunk['pdf_page']}")
                    print(f"   Type: {chunk['type']}")
                    print(f"   Text: {chunk['text'][:300]}...")
            else:
                print(f"No chunks found for clause {clause_id}")
                
        except Exception as e:
            print(f"Error looking up clause: {str(e)}")
    
    def cmd_inspect(self, args: List[str]):
        """List structure and chunk counts."""
        part = None
        if args and args[0] == '--part':
            if len(args) > 1:
                part = args[1]
            else:
                print("Error: --part requires a part identifier")
                return
        
        print("Inspecting database structure...")
        
        self.initialize_systems()
        
        if not self.storage:
            print("Error: Storage not initialized")
            return
        
        try:
            if part:
                # Show chunks for specific part
                chunks = self.storage.get_chunks_by_part(part)
                print(f"\nChunks in part '{part}': {len(chunks)}")
                
                for doc_id in set(c['doc_id'] for c in chunks):
                    doc_chunks = [c for c in chunks if c['doc_id'] == doc_id]
                    print(f"\n  {doc_id}: {len(doc_chunks)} chunks")
            else:
                # Show overall structure
                stats = self.storage.get_statistics()
                
                print(f"\nDatabase Statistics:")
                print(f"  Total chunks: {stats['chunk_count']}")
                print(f"  Total documents: {stats['doc_count']}")
                
                # Show by document
                for doc in self.config.documents:
                    doc_id = doc.get('id', 'unknown')
                    doc_chunks = self.storage.get_chunks_by_doc(doc_id)
                    print(f"\n  {doc_id}:")
                    print(f"    Chunks: {len(doc_chunks)}")
                    
                    # Group by type
                    types = {}
                    for chunk in doc_chunks:
                        chunk_type = chunk.get('type', 'text')
                        types[chunk_type] = types.get(chunk_type, 0) + 1
                    
                    print(f"    Types: {', '.join(f'{k}: {v}' for k, v in types.items())}")
                    
        except Exception as e:
            print(f"Error inspecting database: {str(e)}")


def main():
    """Main entry point for the CLI."""
    # Force UTF-8 on Windows
    force_utf8_console()
    
    # Parse arguments
    args = sys.argv[1:]
    
    # Create CLI instance and run
    cli = CLI()
    cli.run(args)


if __name__ == '__main__':
    main()
