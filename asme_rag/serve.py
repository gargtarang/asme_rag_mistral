"""
ASME RAG Serve Module

This module provides a local web server for the ASME RAG chat interface.
It serves a single static HTML page with inline CSS and JavaScript,
using Server-Sent Events (SSE) for streaming responses.

Usage:
    python -m asme_rag serve

The server binds only to 127.0.0.1 (localhost) on the port specified in config.toml.
Default port: 8765

Security:
    - No external CDN, fonts, or scripts
    - No telemetry
    - Binds only to localhost
    - Uses standard library http.server

Architecture:
    - GET / : Serve the HTML chat page
    - GET /sse : Server-Sent Events endpoint for streaming chat
    - POST /ask : Handle chat questions (fallback for non-SSE clients)
    - GET /static/chat.html : The HTML template (inline in code)
"""

import os
import sys
import json
import logging
import threading
import queue
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote
from html import escape

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asme_rag.utils import get_config, Config
from asme_rag.rag import RAGSystem
from asme_rag.storage import Storage

logger = logging.getLogger(__name__)


class ChatState:
    """Manages chat session state."""
    
    def __init__(self):
        self.sessions = {}
        self.lock = threading.Lock()
        self.config = get_config()
    
    def get_session(self, session_id):
        with self.lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = {
                    'history': [],
                    'last_question': None,
                    'last_excerpts': []
                }
            return self.sessions[session_id]
    
    def add_to_history(self, session_id, question, answer, excerpts, citations):
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id]['history'].append({
                    'question': question,
                    'answer': answer,
                    'excerpts': excerpts,
                    'citations': citations,
                    'timestamp': time.time()
                })
                self.sessions[session_id]['last_question'] = question
                self.sessions[session_id]['last_excerpts'] = excerpts


# Global chat state
chat_state = ChatState()


class SSEClient:
    """Manages an SSE client connection."""
    
    def __init__(self, wfile):
        self.wfile = wfile
        self.connected = True
    
    def send(self, data, event_type="message"):
        """Send an SSE event."""
        if not self.connected:
            return False
        try:
            message = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
            self.wfile.write(message.encode('utf-8'))
            self.wfile.flush()
            return True
        except (BrokenPipeError, ConnectionResetError):
            self.connected = False
            return False


class ChatHTTPRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the chat server."""
    
    # Class-level config
    config = get_config()
    
    def log_message(self, format, *args):
        """Override to use our logger."""
        logger.info(format % args)
    
    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        
        if parsed.path == '/sse':
            self.handle_sse()
        elif parsed.path == '/' or parsed.path == '/index.html':
            self.serve_chat_page()
        elif parsed.path.startswith('/static/'):
            self.serve_static()
        else:
            self.send_error(404, "Not Found")
    
    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)
        
        if parsed.path == '/ask':
            self.handle_ask()
        else:
            self.send_error(404, "Not Found")
    
    def serve_chat_page(self):
        """Serve the main chat HTML page."""
        html = self.generate_html_page()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(html.encode('utf-8'))))
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
    
    def handle_sse(self):
        """Handle Server-Sent Events connection."""
        session_id = self.headers.get('X-Session-ID', 'default')
        
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Cache-Control')
        self.end_headers()
        
        # Send initial connection message
        client = SSEClient(self.wfile)
        client.send({'type': 'connected', 'session_id': session_id})
        
        # Process incoming questions from query params
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        
        if 'q' in params:
            question = unquote(params['q'][0])
            self.process_question_sse(question, session_id, client)
        
        # Keep connection alive for a while
        for _ in range(60):  # ~1 minute
            if not client.connected:
                break
            time.sleep(1)
    
    def process_question_sse(self, question, session_id, client):
        """Process a question with SSE streaming."""
        try:
            # Send start event
            client.send({'type': 'start', 'question': question})
            
            # Get RAG system instance
            config = self.config
            storage = Storage(config)
            qa = RAGSystem(config, storage)
            
            # Perform retrieval
            client.send({'type': 'status', 'message': 'Retrieving excerpts...'})
            retrieval_results = qa.search(question)
            
            # Send excerpts first
            excerpts = []
            for i, result in enumerate(retrieval_results):
                excerpt_data = {
                    'id': i,
                    'text': result.text,
                    'metadata': result.to_dict()
                }
                excerpts.append(excerpt_data)
                client.send({'type': 'excerpt', 'excerpt': excerpt_data})
            
            # Generate answer
            client.send({'type': 'status', 'message': 'Generating answer...'})
            answer = qa.answer_question(question, retrieval_results)
            citations = []
            
            # Check citations
            citation_warnings = []
            
            # Send answer in chunks for streaming effect
            words = answer.split()
            chunk = []
            for word in words:
                chunk.append(word)
                if len(chunk) >= 10:  # Send every 10 words
                    client.send({'type': 'answer_chunk', 'text': ' '.join(chunk) + ' '})
                    chunk = []
            if chunk:
                client.send({'type': 'answer_chunk', 'text': ' '.join(chunk)})
            
            # Send completion
            client.send({
                'type': 'complete',
                'citations': citations,
                'citation_warnings': citation_warnings,
                'excerpts': excerpts
            })
            
            # Store in history
            chat_state.add_to_history(session_id, question, answer, excerpts, citations)
            
        except Exception as e:
            client.send({'type': 'error', 'message': str(e)})
            logger.error(f"Error processing question: {e}")
    
    def handle_ask(self):
        """Handle POST /ask request."""
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
            question = data.get('question', '')
            session_id = data.get('session_id', 'default')
        except:
            self.send_error(400, "Bad Request")
            return
        
        try:
            config = self.config
            storage = Storage(config)
            qa = RAGSystem(config, storage)
            
            # Retrieve and answer
            retrieval_results = qa.search(question)
            answer = qa.answer_question(question, retrieval_results)
            citation_warnings = []
            citations = []
            
            # Format excerpts
            excerpts = []
            for i, result in enumerate(retrieval_results):
                excerpts.append({
                    'id': i,
                    'text': result.text,
                    'metadata': result.to_dict()
                })
            
            response = {
                'answer': answer,
                'citations': citations,
                'citation_warnings': citation_warnings,
                'excerpts': excerpts
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
            # Store in history
            chat_state.add_to_history(session_id, question, answer, excerpts, citations)
            
        except Exception as e:
            self.send_error(500, str(e))
    
    def serve_static(self):
        """Serve static files."""
        # For now, only serve the chat page
        self.serve_chat_page()
    
    def generate_html_page(self):
        """Generate the HTML chat page with inline CSS and JS."""
        return HTML_TEMPLATE


# HTML Template with inline CSS and JavaScript
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ASME RAG Chat</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background-color: #1a1a2e;
            color: #eaeaea;
            line-height: 1.6;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        
        header {
            background-color: #16213e;
            padding: 1rem;
            border-bottom: 2px solid #0f3460;
        }
        
        header h1 {
            font-size: 1.5rem;
            color: #e94560;
        }
        
        header .subtitle {
            color: #a0a0a0;
            font-size: 0.9rem;
        }
        
        .container {
            flex: 1;
            display: flex;
            flex-direction: column;
            max-width: 1200px;
            margin: 0 auto;
            padding: 1rem;
            width: 100%;
        }
        
        .chat-container {
            flex: 1;
            display: flex;
            flex-direction: column;
            background-color: #16213e;
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid #0f3460;
        }
        
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 1rem;
            max-height: 60vh;
        }
        
        .message {
            margin-bottom: 1rem;
            padding: 0.75rem 1rem;
            border-radius: 6px;
            animation: fadeIn 0.3s ease;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .message.user {
            background-color: #0f3460;
            border-bottom-right-radius: 0;
            color: #fff;
        }
        
        .message.assistant {
            background-color: #1a1a2e;
            border-bottom-left-radius: 0;
        }
        
        .message.system {
            background-color: #0f3460;
            font-size: 0.85rem;
            color: #a0c4ff;
        }
        
        .message.error {
            background-color: #e94560;
            color: white;
        }
        
        .excerpts-section {
            margin-top: 0.5rem;
            padding: 0.75rem;
            background-color: rgba(15, 52, 96, 0.3);
            border-radius: 6px;
            border-left: 3px solid #0f3460;
        }
        
        .excerpt {
            margin-bottom: 0.75rem;
            padding: 0.5rem;
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 4px;
            font-size: 0.85rem;
        }
        
        .excerpt-meta {
            color: #a0a0a0;
            font-size: 0.75rem;
            margin-bottom: 0.25rem;
        }
        
        .citation {
            color: #e94560;
            font-family: monospace;
            font-size: 0.85rem;
        }
        
        .citation-warning {
            color: #ffcc00;
            font-weight: bold;
        }
        
        .answer-streaming {
            color: #a0c4ff;
        }
        
        .input-area {
            display: flex;
            gap: 0.5rem;
            padding: 1rem;
            background-color: #1a1a2e;
            border-top: 1px solid #0f3460;
        }
        
        .input-area input {
            flex: 1;
            padding: 0.75rem 1rem;
            border: 1px solid #0f3460;
            border-radius: 6px;
            background-color: #16213e;
            color: #eaeaea;
            font-size: 1rem;
        }
        
        .input-area input:focus {
            outline: none;
            border-color: #e94560;
        }
        
        .input-area input::placeholder {
            color: #6c757d;
        }
        
        .input-area button {
            padding: 0.75rem 1.5rem;
            background-color: #e94560;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 1rem;
            transition: background-color 0.2s;
        }
        
        .input-area button:hover {
            background-color: #c81e45;
        }
        
        .input-area button:disabled {
            background-color: #6c757d;
            cursor: not-allowed;
        }
        
        .history-sidebar {
            position: fixed;
            right: 0;
            top: 0;
            bottom: 0;
            width: 250px;
            background-color: #1a1a2e;
            border-left: 1px solid #0f3460;
            overflow-y: auto;
            padding: 1rem;
            display: none;
        }
        
        .history-sidebar visible {
            display: block;
        }
        
        .history-item {
            padding: 0.5rem;
            border-bottom: 1px solid #0f3460;
            cursor: pointer;
            color: #a0c4ff;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .history-item:hover {
            background-color: #0f3460;
            color: white;
        }
        
        .toggle-history {
            position: fixed;
            right: 1rem;
            top: 1rem;
            background-color: #0f3460;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            cursor: pointer;
            z-index: 1000;
        }
        
        .status-bar {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background-color: #0f3460;
            color: #a0c4ff;
            padding: 0.5rem 1rem;
            font-size: 0.85rem;
            display: flex;
            justify-content: space-between;
        }
        
        .typing-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            background-color: #e94560;
            border-radius: 50%;
            margin: 0 2px;
            animation: pulse 1s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        
        .expand-buttons {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            margin-top: 0.5rem;
        }
        
        .expand-btn {
            padding: 0.25rem 0.5rem;
            background-color: #0f3460;
            color: #a0c4ff;
            border: 1px solid #16213e;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.8rem;
        }
        
        .expand-btn:hover {
            background-color: #16213e;
            color: white;
        }
        
        .link {
            color: #a0c4ff;
            text-decoration: underline;
            cursor: pointer;
        }
        
        .link:hover {
            color: #e94560;
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 0.5rem;
            }
            
            .history-sidebar {
                width: 100%;
                top: auto;
                bottom: 0;
                height: 200px;
                border-left: none;
                border-top: 1px solid #0f3460;
            }
            
            .toggle-history {
                top: auto;
                bottom: 200px;
            }
        }
    </style>
</head>
<body>
    <header>
        <h1>ASME RAG Chat</h1>
        <div class="subtitle">Offline ASME BPVC Retrieval-Augmented Generation</div>
    </header>
    
    <div class="container">
        <button class="toggle-history" onclick="toggleHistory()">History</button>
        
        <div class="history-sidebar" id="historySidebar">
            <h3 style="color: #e94560; margin-bottom: 1rem;">History</h3>
            <div id="historyList"></div>
        </div>
        
        <div class="chat-container">
            <div class="chat-messages" id="chatMessages">
                <div class="message system">
                    <strong>Welcome to ASME RAG Chat</strong><br>
                    Ask questions about ASME BPVC standards. All answers are grounded in retrieved excerpts with citations.
                </div>
            </div>
            
            <div class="input-area">
                <input 
                    type="text" 
                    id="questionInput" 
                    placeholder="Ask about ASME BPVC, vacuum design, nozzle reinforcement..." 
                    onkeydown="handleKeyDown(event)"
                >
                <button onclick="askQuestion()" id="sendBtn">Send</button>
            </div>
        </div>
    </div>
    
    <div class="status-bar">
        <span id="statusText">Ready</span>
        <span id="typingIndicator"></span>
    </div>
    
    <script>
        // Session management
        const sessionId = 'session_' + Math.random().toString(36).substr(2, 9);
        let currentStreaming = false;
        let eventSource = null;
        
        // DOM elements
        const chatMessages = document.getElementById('chatMessages');
        const questionInput = document.getElementById('questionInput');
        const sendBtn = document.getElementById('sendBtn');
        const statusText = document.getElementById('statusText');
        const typingIndicator = document.getElementById('typingIndicator');
        const historyList = document.getElementById('historyList');
        const historySidebar = document.getElementById('historySidebar');
        
        // History
        let history = [];
        
        // Toggle history sidebar
        function toggleHistory() {
            historySidebar.style.display = historySidebar.style.display === 'block' ? 'none' : 'block';
        }
        
        // Add message to chat
        function addMessage(content, type = 'assistant') {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message ' + type;
            messageDiv.innerHTML = content;
            chatMessages.appendChild(messageDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
            return messageDiv;
        }
        
        // Update history list
        function updateHistory() {
            historyList.innerHTML = '';
            history.forEach((item, index) => {
                const div = document.createElement('div');
                div.className = 'history-item';
                div.textContent = item.question.substring(0, 50) + (item.question.length > 50 ? '...' : '');
                div.onclick = () => loadFromHistory(index);
                historyList.appendChild(div);
            });
        }
        
        // Load from history
        function loadFromHistory(index) {
            const item = history[index];
            questionInput.value = item.question;
            toggleHistory();
            questionInput.focus();
        }
        
        // Add to history
        function addToHistory(question, answer, excerpts, citations) {
            history.unshift({
                question: question,
                answer: answer,
                excerpts: excerpts,
                citations: citations
            });
            if (history.length > 50) {
                history.pop();
            }
            updateHistory();
        }
        
        // Handle key down
        function handleKeyDown(event) {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                askQuestion();
            }
        }
        
        // Close existing SSE connection
        function closeSSE() {
            if (eventSource) {
                eventSource.close();
                eventSource = null;
            }
            currentStreaming = false;
            updateStatus();
        }
        
        // Update status bar
        function updateStatus() {
            if (currentStreaming) {
                statusText.textContent = 'Streaming...';
                typingIndicator.innerHTML = '<span class="typing-indicator"></span><span class="typing-indicator"></span><span class="typing-indicator"></span>';
                sendBtn.disabled = true;
            } else {
                statusText.textContent = 'Ready';
                typingIndicator.innerHTML = '';
                sendBtn.disabled = false;
            }
        }
        
        // Ask a question using SSE
        function askQuestion() {
            const question = questionInput.value.trim();
            if (!question) return;
            
            // Clear input
            questionInput.value = '';
            
            // Add user message
            addMessage(escapeHtml(question), 'user');
            
            // Create assistant message container
            const assistantMsg = addMessage('<span class="answer-streaming">Thinking...</span>', 'assistant');
            
            // Close any existing connection
            closeSSE();
            
            currentStreaming = true;
            updateStatus();
            
            // Create SSE connection
            const url = '/sse?q=' + encodeURIComponent(question) + '&session_id=' + sessionId;
            eventSource = new EventSource(url);
            
            let answerText = '';
            let excerpts = [];
            let citations = [];
            let citationWarnings = [];
            
            eventSource.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    
                    switch (data.type) {
                        case 'connected':
                            console.log('SSE connected, session:', data.session_id);
                            break;
                            
                        case 'start':
                            console.log('Starting to process:', data.question);
                            break;
                            
                        case 'status':
                            assistantMsg.innerHTML = '<span class="answer-streaming">' + escapeHtml(data.message) + '</span>';
                            break;
                            
                        case 'excerpt':
                            excerpts.push(data.excerpt);
                            // Don't show excerpts yet, wait for answer
                            break;
                            
                        case 'answer_chunk':
                            answerText += data.text;
                            assistantMsg.innerHTML = '<span class="answer-streaming">' + escapeHtml(answerText) + '</span>';
                            break;
                            
                        case 'complete':
                            answerText += data.text || '';
                            citations = data.citations || [];
                            citationWarnings = data.citation_warnings || [];
                            
                            // Format the final answer
                            let answerHtml = escapeHtml(answerText);
                            
                            // Add citations if any
                            if (citations.length > 0) {
                                answerHtml += '<div style="margin-top: 0.5rem;"><strong>Citations:</strong> ';
                                answerHtml += citations.map(c => '<span class="citation">' + escapeHtml(c) + '</span>').join(', ');
                                answerHtml += '</div>';
                            }
                            
                            // Add citation warnings
                            if (citationWarnings.length > 0) {
                                answerHtml += '<div style="margin-top: 0.5rem; color: #ffcc00;">';
                                answerHtml += '<strong>Citation Warnings:</strong> ';
                                answerHtml += citationWarnings.map(w => '<span class="citation-warning">' + escapeHtml(w) + '</span>').join(', ');
                                answerHtml += '</div>';
                            }
                            
                            // Show excerpts
                            if (excerpts.length > 0) {
                                answerHtml += '<div class="excerpts-section"><strong>Retrieved Excerpts:</strong>';
                                excerpts.forEach(excerpt => {
                                    const meta = excerpt.metadata || {};
                                    const clause = meta.clause_id || 'Unknown';
                                    const page = meta.pdf_page || '?';
                                    const code = meta.code || 'ASME';
                                    const edition = meta.edition || '2025';
                                    
                                    answerHtml += '<div class="excerpt">';
                                    answerHtml += '<div class="excerpt-meta">[' + escapeHtml(code) + ' ' + escapeHtml(edition) + ', ' + escapeHtml(clause) + ', PDF p.' + escapeHtml(page) + ']</div>';
                                    answerHtml += '<div>' + escapeHtml(excerpt.text.substring(0, 500)) + (excerpt.text.length > 500 ? '...' : '') + '</div>';
                                    answerHtml += '</div>';
                                });
                                answerHtml += '</div>';
                            }
                            
                            assistantMsg.innerHTML = answerHtml;
                            
                            // Add to history
                            addToHistory(question, answerText, excerpts, citations);
                            
                            currentStreaming = false;
                            updateStatus();
                            closeSSE();
                            break;
                            
                        case 'error':
                            assistantMsg.innerHTML = '<span style="color: #ff6b6b;">Error: ' + escapeHtml(data.message) + '</span>';
                            currentStreaming = false;
                            updateStatus();
                            closeSSE();
                            break;
                    }
                } catch (e) {
                    console.error('Error parsing SSE message:', e);
                }
            };
            
            eventSource.onerror = function() {
                if (!currentStreaming) return;
                assistantMsg.innerHTML = '<span style="color: #ff6b6b;">Connection error. Please try again.</span>';
                currentStreaming = false;
                updateStatus();
                closeSSE();
            };
        }
        
        // Escape HTML
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // Initialize
        addMessage('This is an <strong>offline</strong> chat interface. All answers are generated from your local ASME PDFs with proper citations.', 'system');
        updateHistory();
        
        // Focus input on load
        window.onload = function() {
            questionInput.focus();
        };
        
        // Handle window close
        window.onbeforeunload = function() {
            closeSSE();
        };
    </script>
</body>
</html>
"""


def serve(config: Config = None):
    """
    Start the local web server for ASME RAG chat.
    
    Args:
        config: Configuration object. If None, loads from config.toml.
    """
    if config is None:
        config = get_config()
    
    # Get server configuration
    host = config.serve.host if hasattr(config.serve, 'host') else '127.0.0.1'
    port = config.serve.port if hasattr(config.serve, 'port') else 8765
    
    # Configure handler
    ChatHTTPRequestHandler.config = config
    
    # Create server
    server_address = (host, port)
    httpd = HTTPServer(server_address, ChatHTTPRequestHandler)
    
    logger.info(f"Starting ASME RAG server on {host}:{port}")
    logger.info(f"Open in browser: http://{host}:{port}")
    logger.info("Press Ctrl+C to stop")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


def main():
    """Main entry point for the serve command."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Start ASME RAG local web server')
    parser.add_argument('--host', default=None, help='Host to bind to (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=None, help='Port to listen on (default: 8765)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load config
    config = get_config()
    
    # Override with command line args
    if args.host:
        config.serve.host = args.host
    if args.port:
        config.serve.port = args.port
    
    # Start server
    serve(config)


if __name__ == '__main__':
    main()
