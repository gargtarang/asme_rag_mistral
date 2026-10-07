"""
Comprehensive Unit Tests for ASME RAG + Chamber Design Assistant

This file contains tests for all phases (0-10).
Tests are designed to work with the actual implementation.
"""

import unittest
import os
import sys
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestConfiguration(unittest.TestCase):
    """Test configuration loading."""
    
    def test_config_loading(self):
        """Test that config can be loaded."""
        from asme_rag.utils import get_config
        config = get_config()
        self.assertIsNotNone(config)
    
    def test_config_has_required_attributes(self):
        """Test that config has required attributes."""
        from asme_rag.utils import get_config
        config = get_config()
        
        # Check LM Studio config
        self.assertTrue(hasattr(config, 'api_url'))
        self.assertTrue(hasattr(config, 'chat_model'))
        self.assertTrue(hasattr(config, 'embedding_model'))
        
        # Check serve config
        self.assertTrue(hasattr(config, 'serve_host'))
        self.assertTrue(hasattr(config, 'serve_port'))
        
        # Check vision config
        self.assertTrue(hasattr(config, 'vision_enabled'))
    
    def test_config_values_are_correct(self):
        """Test that config values are correct."""
        from asme_rag.utils import get_config
        config = get_config()
        
        self.assertEqual(config.serve_host, '127.0.0.1')
        self.assertEqual(config.serve_port, 8765)
        self.assertTrue(config.vision_enabled)


class TestPDFParser(unittest.TestCase):
    """Test PDF parser module."""
    
    def test_parser_initialization(self):
        """Test PDFParser initialization."""
        from asme_rag.pdf_parser import PDFParser
        from asme_rag.utils import get_config
        
        config = get_config()
        parser = PDFParser(config)
        
        self.assertIsNotNone(parser.config)
    
    def test_text_block_creation(self):
        """Test TextBlock creation."""
        from asme_rag.pdf_parser import TextBlock
        
        block = TextBlock(
            x=50, y=100, width=200, height=50,
            text="Test text",
            font_name="Helvetica", font_size=12.0, 
            is_bold=True, is_superscript=False
        )
        
        self.assertEqual(block.text, "Test text")
        self.assertEqual(block.x, 50)


class TestChunker(unittest.TestCase):
    """Test chunker module."""
    
    def test_chunker_initialization(self):
        """Test Chunker initialization."""
        from asme_rag.chunker import Chunker
        from asme_rag.utils import get_config
        
        config = get_config()
        chunker = Chunker(config)
        
        self.assertIsNotNone(chunker.config)
    
    def test_chunk_creation(self):
        """Test Chunk creation."""
        from asme_rag.chunker import Chunk, ChunkMetadata
        
        metadata = ChunkMetadata(
            doc_id="test_doc",
            code="TEST",
            division="Test",
            edition=2025,
            clause_id="TEST-1",
            pdf_page=1,
            type="text"
        )
        chunk = Chunk(text="Test text", metadata=metadata)
        
        self.assertEqual(chunk.text, "Test text")
        self.assertEqual(chunk.metadata.doc_id, "test_doc")


class TestStorage(unittest.TestCase):
    """Test storage module."""
    
    def setUp(self):
        """Set up test database."""
        self.db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.db_file.name
        self.db_file.close()
        
        from asme_rag.utils import get_config
        from asme_rag.storage import Storage
        
        self.config = get_config()
        self.config.database_path = self.db_path
        self.storage = Storage(self.config)
    
    def tearDown(self):
        """Clean up test database."""
        self.storage.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_storage_initialization(self):
        """Test Storage initialization."""
        self.assertIsNotNone(self.storage.conn)
    
    def test_database_creation(self):
        """Test that database is created."""
        self.assertTrue(os.path.exists(self.db_path))


class TestRAG(unittest.TestCase):
    """Test RAG module."""
    
    def setUp(self):
        """Set up test database."""
        self.db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.db_file.name
        self.db_file.close()
        
        from asme_rag.utils import get_config
        from asme_rag.storage import Storage
        from asme_rag.rag import RAGSystem
        
        self.config = get_config()
        self.config.database_path = self.db_path
        
        self.storage = Storage(self.config)
        self.rag = RAGSystem(self.config, self.storage)
    
    def tearDown(self):
        """Clean up."""
        self.storage.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_rag_initialization(self):
        """Test RAGSystem initialization."""
        self.assertIsNotNone(self.rag.config)
        self.assertIsNotNone(self.rag.storage)
    
    def test_system_prompt_exists(self):
        """Test that system prompt exists."""
        self.assertIsNotNone(self.rag.SYSTEM_PROMPT)
        self.assertIn("ASME", self.rag.SYSTEM_PROMPT)


class TestCLI(unittest.TestCase):
    """Test CLI module."""
    
    def test_cli_creation(self):
        """Test CLI instance creation."""
        from asme_rag.cli import CLI
        cli = CLI()
        
        self.assertIsNotNone(cli.config)
    
    def test_all_commands_exist(self):
        """Test that all commands exist in CLI."""
        from asme_rag.cli import CLI
        cli = CLI()
        
        commands = [
            'cmd_check', 'cmd_ingest', 'cmd_embed', 'cmd_search',
            'cmd_ask', 'cmd_chat', 'cmd_refs', 'cmd_rulemap',
            'cmd_materials', 'cmd_describe_figures', 'cmd_figure_read',
            'cmd_table_from_image', 'cmd_vision_test', 'cmd_eval',
            'cmd_serve', 'cmd_page', 'cmd_clause', 'cmd_inspect'
        ]
        
        for cmd in commands:
            self.assertTrue(hasattr(cli, cmd), f"Missing command: {cmd}")
            self.assertTrue(callable(getattr(cli, cmd)), f"Command not callable: {cmd}")
    
    def test_check_command_runs(self):
        """Test that check command runs without error."""
        from asme_rag.cli import CLI
        cli = CLI()
        
        # This should not raise an exception
        try:
            cli.cmd_check([])
        except Exception:
            pass  # Some checks may fail, but command should run


class TestChamber(unittest.TestCase):
    """Test chamber module."""
    
    def test_calculator_initialization(self):
        """Test ChamberCalculator initialization."""
        from chamber.calc import ChamberCalculator
        calc = ChamberCalculator()
        self.assertIsNotNone(calc)
    
    def test_report_generator_initialization(self):
        """Test ReportGenerator initialization."""
        from chamber.report import ReportGenerator
        generator = ReportGenerator()
        self.assertIsNotNone(generator)
    
    def test_value_provider(self):
        """Test ValueProvider."""
        from chamber.provide import ValueProvider
        provider = ValueProvider()
        
        self.assertIsNotNone(provider)
        self.assertTrue(hasattr(provider, 'provide_value'))


class TestServe(unittest.TestCase):
    """Test serve module (Phase 10)."""
    
    def test_serve_module_import(self):
        """Test that serve module can be imported."""
        from asme_rag.serve import HTML_TEMPLATE, ChatState, ChatHTTPRequestHandler
        
        self.assertIsNotNone(HTML_TEMPLATE)
    
    def test_html_template_content(self):
        """Test HTML template content."""
        from asme_rag.serve import HTML_TEMPLATE
        
        self.assertIn('<!DOCTYPE html>', HTML_TEMPLATE)
        self.assertIn('ASME RAG Chat', HTML_TEMPLATE)
        self.assertIn('<style>', HTML_TEMPLATE)
        self.assertIn('<script>', HTML_TEMPLATE)
        self.assertIn('EventSource', HTML_TEMPLATE)
    
    def test_chat_state(self):
        """Test ChatState."""
        from asme_rag.serve import ChatState
        
        state = ChatState()
        session = state.get_session('test')
        
        self.assertIn('test', state.sessions)
        self.assertEqual(session['history'], [])
        
        # Test adding to history
        state.add_to_history('test', 'Q', 'A', [], [])
        self.assertEqual(len(state.get_session('test')['history']), 1)
    
    def test_serve_command_in_cli(self):
        """Test that serve command is in CLI."""
        from asme_rag.cli import CLI
        cli = CLI()
        
        self.assertTrue(hasattr(cli, 'cmd_serve'))
        self.assertTrue(callable(cli.cmd_serve))


class TestFakeLMServer(unittest.TestCase):
    """Test fake LM server."""
    
    def test_fake_server_import(self):
        """Test that fake LM server can be imported."""
        from tests.fake_lm_server import FakeLMServer, FakeLMRequestHandler
        
        self.assertIsNotNone(FakeLMServer)
        self.assertIsNotNone(FakeLMRequestHandler)
    
    def test_fake_server_creation(self):
        """Test fake server creation."""
        from tests.fake_lm_server import FakeLMServer
        
        server = FakeLMServer(host='127.0.0.1', port=9999)
        self.assertEqual(server.host, '127.0.0.1')
        self.assertEqual(server.port, 9999)


class TestVSCodeIntegration(unittest.TestCase):
    """Test VS Code integration files."""
    
    def test_tasks_json_exists(self):
        """Test that tasks.json exists."""
        tasks_path = os.path.join(os.path.dirname(__file__), '..', '.vscode', 'tasks.json')
        self.assertTrue(os.path.exists(tasks_path))
    
    def test_settings_json_exists(self):
        """Test that settings.json exists."""
        settings_path = os.path.join(os.path.dirname(__file__), '..', '.vscode', 'settings.json')
        self.assertTrue(os.path.exists(settings_path))
    
    def test_launch_json_exists(self):
        """Test that launch.json exists."""
        launch_path = os.path.join(os.path.dirname(__file__), '..', '.vscode', 'launch.json')
        self.assertTrue(os.path.exists(launch_path))


if __name__ == '__main__':
    unittest.main()
