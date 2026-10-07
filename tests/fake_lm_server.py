"""
Fake LM Studio Server for Offline Testing

This module provides a fake OpenAI-compatible API server for testing
without requiring actual LM Studio connectivity.

Usage:
    python -m tests.fake_lm_server

The server runs on localhost:1234 by default and provides:
- /v1/chat/completions - returns canned responses
- /v1/embeddings - returns mock embeddings
- Supports image_url in messages for vision testing
"""

import json
import base64
import random
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from io import BytesIO
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class FakeLMServer:
    """Fake LM Studio server that mimics OpenAI API endpoints."""
    
    def __init__(self, host='127.0.0.1', port=1234):
        self.host = host
        self.port = port
        self.server = None
        self.server_thread = None
        self.running = False
        
    def start(self):
        """Start the fake server in a background thread."""
        if self.running:
            return
        
        self.server = HTTPServer((self.host, self.port), FakeLMRequestHandler)
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        self.running = True
        print(f"Fake LM Studio server started on {self.host}:{self.port}")
        
    def stop(self):
        """Stop the fake server."""
        if self.running:
            self.server.shutdown()
            self.server_thread.join(timeout=1)
            self.running = False
            print("Fake LM Studio server stopped")


class FakeLMRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for fake LM Studio API."""
    
    # Mock embedding dimension (matches nomic-embed-text-v1.5)
    EMBEDDING_DIM = 768
    
    # Mock responses
    MOCK_CHAT_RESPONSES = {
        "default": {
            "id": "chatcmpl-fake",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "gemma-4-26b-a4b",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "This is a mock response from the fake LM Studio server. "
                               "In production, this would be a real response from LM Studio."
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
        },
        "vision": {
            "id": "chatcmpl-fake-vision",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "gemma-4-26b-a4b",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "(model-generated figure description, unverified) "
                               "This is a mock figure description. "
                               "Figure shows multiple curves with labels. "
                               "Axis labels: X-axis (mm), Y-axis (MPa). "
                               "Note: All values are UNVERIFIED until confirmed by user."
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 15,
                "completion_tokens": 30,
                "total_tokens": 45
            }
        },
        "asme": {
            "id": "chatcmpl-fake-asme",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "gemma-4-26b-a4b",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Answer ONLY from the numbered excerpts provided.\n\n"
                               "Cite every statement as [code, edition, clause, PDF p.N].\n\n"
                               "not found: Please consult ASME BPVC VIII-1, 2025 edition, "
                               "Paragraph UG-37 for vacuum design rules.\n\n"
                               "Verify: Check UG-37 in ASME BPVC VIII-1 2025 PDF page 123"
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 20,
                "completion_tokens": 40,
                "total_tokens": 60
            }
        }
    }
    
    def log_message(self, format, *args):
        """Suppress default logging."""
        pass
    
    def do_POST(self):
        """Handle POST requests."""
        try:
            parsed = urlparse(self.path)
            
            # Handle chat completions
            if parsed.path == '/v1/chat/completions':
                self.handle_chat_completions()
                return
            
            # Handle embeddings
            elif parsed.path == '/v1/embeddings':
                self.handle_embeddings()
                return
            
            # Unknown endpoint
            else:
                self.send_error(404, f"Endpoint {parsed.path} not found")
                return
                
        except Exception as e:
            self.send_error(500, f"Internal server error: {str(e)}")
    
    def handle_chat_completions(self):
        """Handle /v1/chat/completions endpoint."""
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            request_data = json.loads(post_data)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        
        # Check if this is a vision request (has image_url)
        has_image = False
        if 'messages' in request_data:
            for message in request_data['messages']:
                if 'content' in message:
                    content = message['content']
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get('type') == 'image_url':
                                has_image = True
                                break
        
        # Select appropriate mock response
        if has_image:
            response_data = self.MOCK_CHAT_RESPONSES['vision']
        elif 'asme' in request_data.get('model', '').lower():
            response_data = self.MOCK_CHAT_RESPONSES['asme']
        else:
            response_data = self.MOCK_CHAT_RESPONSES['default']
        
        # Send response
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response_data).encode('utf-8'))
    
    def handle_embeddings(self):
        """Handle /v1/embeddings endpoint."""
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            request_data = json.loads(post_data)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        
        # Generate mock embeddings
        if 'input' in request_data:
            input_data = request_data['input']
            if isinstance(input_data, str):
                texts = [input_data]
            else:
                texts = input_data
            
            embeddings = []
            for text in texts:
                # Generate deterministic mock embedding based on text
                embedding = self.generate_mock_embedding(text)
                embeddings.append(embedding)
            
            response_data = {
                "object": "list",
                "data": [
                    {
                        "object": "embedding",
                        "embedding": embedding,
                        "index": i
                    }
                    for i, embedding in enumerate(embeddings)
                ],
                "model": self.EMBEDDING_DIM,
                "usage": {
                    "prompt_tokens": sum(len(text.split()) for text in texts),
                    "total_tokens": sum(len(text.split()) for text in texts)
                }
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
        else:
            self.send_error(400, "Missing 'input' field")
    
    def generate_mock_embedding(self, text):
        """Generate a deterministic mock embedding for testing."""
        # Use hash of text to generate deterministic values
        text_bytes = text.encode('utf-8')
        text_hash = hash(text_bytes)
        
        # Generate embedding values based on hash
        random.seed(text_hash)
        embedding = [random.uniform(-1, 1) for _ in range(self.EMBEDDING_DIM)]
        
        return embedding


def main():
    """Main function to start the fake server."""
    server = FakeLMServer()
    server.start()
    
    try:
        # Keep server running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()


if __name__ == '__main__':
    main()
