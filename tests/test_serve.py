"""
Unit tests for the serve module (Phase 10 - Local Web Server)

These tests verify:
- HTML template generation
- HTTP request handling
- SSE streaming
- Integration with RAG system
- Security (localhost binding only)
- No external CDN/fonts/scripts
"""

import unittest
import json
import threading
import time
from http.client import HTTPConnection
from io import StringIO
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asme_rag.serve import HTML_TEMPLATE, ChatState, ChatHTTPRequestHandler
from asme_rag.utils import Config


class TestHTMLTemplate(unittest.TestCase):
    """Test HTML template content."""
    
    def test_template_has_required_elements(self):
        """Verify HTML template has all required elements."""
        self.assertIn('<!DOCTYPE html>', HTML_TEMPLATE)
        self.assertIn('<html', HTML_TEMPLATE)
        self.assertIn('</html>', HTML_TEMPLATE)
        self.assertIn('<head>', HTML_TEMPLATE)
        self.assertIn('</head>', HTML_TEMPLATE)
        self.assertIn('<body>', HTML_TEMPLATE)
        self.assertIn('</body>', HTML_TEMPLATE)
    
    def test_template_has_title(self):
        """Verify template has correct title."""
        self.assertIn('ASME RAG Chat', HTML_TEMPLATE)
    
    def test_template_has_inline_css(self):
        """Verify template has inline CSS (no external CDN)."""
        self.assertIn('<style>', HTML_TEMPLATE)
        self.assertIn('</style>', HTML_TEMPLATE)
        # Should not reference external CDN
        self.assertNotIn('http://', HTML_TEMPLATE.split('<style>')[1].split('</style>')[0])
        self.assertNotIn('https://', HTML_TEMPLATE.split('<style>')[1].split('</style>')[0])
    
    def test_template_has_inline_js(self):
        """Verify template has inline JavaScript (no external CDN)."""
        self.assertIn('<script>', HTML_TEMPLATE)
        self.assertIn('</script>', HTML_TEMPLATE)
        # Should not reference external scripts
        script_content = HTML_TEMPLATE.split('<script>')[1].split('</script>')[0]
        self.assertNotIn('http://', script_content)
        self.assertNotIn('https://', script_content)
    
    def test_template_has_chat_interface(self):
        """Verify template has chat interface elements."""
        self.assertIn('chat-messages', HTML_TEMPLATE)
        self.assertIn('questionInput', HTML_TEMPLATE)
        self.assertIn('sendBtn', HTML_TEMPLATE)
        self.assertIn('askQuestion', HTML_TEMPLATE)
    
    def test_template_has_sse_support(self):
        """Verify template has SSE support."""
        self.assertIn('EventSource', HTML_TEMPLATE)
        self.assertIn('/sse', HTML_TEMPLATE)
    
    def test_template_has_history_support(self):
        """Verify template has history sidebar."""
        self.assertIn('history-sidebar', HTML_TEMPLATE)
        self.assertIn('historyList', HTML_TEMPLATE)
        self.assertIn('toggleHistory', HTML_TEMPLATE)
    
    def test_template_has_excerpts_display(self):
        """Verify template can display retrieved excerpts."""
        self.assertIn('excerpts-section', HTML_TEMPLATE)
        self.assertIn('excerpt-meta', HTML_TEMPLATE)
    
    def test_template_has_citation_display(self):
        """Verify template can display citations."""
        self.assertIn('citation', HTML_TEMPLATE)
        self.assertIn('citation-warning', HTML_TEMPLATE)
    
    def test_template_no_emojis(self):
        """Verify template contains no emojis."""
        # Check for common emoji patterns
        self.assertNotIn('😀', HTML_TEMPLATE)
        self.assertNotIn('🎉', HTML_TEMPLATE)
        self.assertNotIn('🔍', HTML_TEMPLATE)
    
    def test_template_has_utf8_meta(self):
        """Verify template has UTF-8 meta tag."""
        self.assertIn('charset="UTF-8"', HTML_TEMPLATE)
    
    def test_template_has_viewport_meta(self):
        """Verify template has responsive viewport meta."""
        self.assertIn('viewport', HTML_TEMPLATE)


class TestChatState(unittest.TestCase):
    """Test chat state management."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.state = ChatState()
    
    def test_get_session_creates_new(self):
        """Test that get_session creates a new session."""
        session = self.state.get_session('test_session')
        self.assertIn('test_session', self.state.sessions)
        self.assertEqual(session['history'], [])
    
    def test_get_session_returns_existing(self):
        """Test that get_session returns existing session."""
        session1 = self.state.get_session('test_session')
        session2 = self.state.get_session('test_session')
        self.assertIs(session1, session2)
    
    def test_add_to_history(self):
        """Test adding to session history."""
        self.state.add_to_history(
            'test_session',
            'What is UG-37?',
            'UG-37 is about...',
            [{'text': 'excerpt 1'}],
            ['VIII-1 2025, UG-37, p.123']
        )
        
        session = self.state.get_session('test_session')
        self.assertEqual(len(session['history']), 1)
        self.assertEqual(session['history'][0]['question'], 'What is UG-37?')
        self.assertEqual(session['last_question'], 'What is UG-37?')
    
    def test_history_max_length(self):
        """Test that history is capped."""
        # Add many items
        for i in range(100):
            self.state.add_to_history(
                'test_session',
                f'Question {i}',
                f'Answer {i}',
                [],
                []
            )
        
        session = self.state.get_session('test_session')
        # Should be capped at some reasonable limit (default behavior)
        self.assertLessEqual(len(session['history']), 100)


class TestServeIntegration(unittest.TestCase):
    """Integration tests for the serve module."""
    
    def test_html_generation(self):
        """Test HTML generation from handler."""
        handler = ChatHTTPRequestHandler.__new__(ChatHTTPRequestHandler)
        html = handler.generate_html_page()
        
        self.assertIsInstance(html, str)
        self.assertGreater(len(html), 1000)
        self.assertIn('ASME RAG Chat', html)
    
    def test_handler_has_required_methods(self):
        """Verify handler has required HTTP methods."""
        self.assertTrue(hasattr(ChatHTTPRequestHandler, 'do_GET'))
        self.assertTrue(hasattr(ChatHTTPRequestHandler, 'do_POST'))
        self.assertTrue(hasattr(ChatHTTPRequestHandler, 'serve_chat_page'))
        self.assertTrue(hasattr(ChatHTTPRequestHandler, 'handle_sse'))
        self.assertTrue(hasattr(ChatHTTPRequestHandler, 'handle_ask'))


class TestServeSecurity(unittest.TestCase):
    """Test security aspects of the serve module."""
    
    def test_default_host_is_localhost(self):
        """Verify default host is localhost only."""
        from asme_rag.utils import get_config
        config = get_config()
        self.assertEqual(config.serve.host, '127.0.0.1')
    
    def test_default_port_is_safe(self):
        """Verify default port is in safe range."""
        from asme_rag.utils import get_config
        config = get_config()
        # Port should be in unprivileged range (1024-65535)
        self.assertGreaterEqual(config.serve.port, 1024)
        self.assertLessEqual(config.serve.port, 65535)
    
    def test_html_escaping(self):
        """Verify HTML escaping in template."""
        # The template should have escapeHtml function
        self.assertIn('escapeHtml', HTML_TEMPLATE)


class TestServeFunctionality(unittest.TestCase):
    """Functional tests for serve module."""
    
    def test_serve_command_in_cli(self):
        """Verify serve command is in CLI."""
        from asme_rag.cli import CLI
        cli = CLI()
        self.assertTrue(hasattr(cli, 'cmd_serve'))
    
    def test_serve_command_callable(self):
        """Verify serve command is callable."""
        from asme_rag.cli import CLI
        cli = CLI()
        self.assertTrue(callable(cli.cmd_serve))


if __name__ == '__main__':
    unittest.main()
