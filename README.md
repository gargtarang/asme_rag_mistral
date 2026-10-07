# ASME RAG with Mistral

A Retrieval-Augmented Generation (RAG) pipeline for querying **ASME standards and technical documents** using **Mistral AI** models.

## Overview

This project lets you ask natural-language questions about ASME documents (e.g., codes, standards, technical specs) and get answers grounded in the actual document content, with source citations to reduce hallucinations.

The pipeline:

1. **Ingest** ASME documents (PDF/DOCX/TXT).
2. **Chunk** the text into overlapping passages.
3. **Embed** the chunks using a Mistral embedding model.
4. **Store** the vectors in a vector database.
5. **Retrieve** the top relevant chunks for a user query.
6. **Generate** a grounded answer with a Mistral LLM, citing the sources used.

## Features

- Document ingestion and preprocessing
- Semantic search over ASME document content
- Grounded, cited answers via Mistral AI
- Simple query interface

## Getting Started

### Prerequisites

- Python 3.10+
- A Mistral AI API key ([console.mistral.ai](https://console.mistral.ai))

### Installation

```bash
git clone https://github.com/gargtarang/asme_rag_mistral.git
cd asme_rag_mistral
pip install -r requirements.txt
```

### Configuration

Set your API key:

```bash
export MISTRAL_API_KEY="your-api-key"
```

### Usage

1. Place your ASME documents in the `docs/` folder.
2. Run the ingestion pipeline to build the index.
3. Ask questions:

```bash
python query.py "What are the requirements for welded joints in ASME BPVC Section IX?"
```

## Project Structure

```
asme_rag_mistral/
├── docs/            # Source ASME documents
├── ingest.py        # Document ingestion & indexing
├── query.py         # Query interface
└── requirements.txt
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Acknowledgments

- [Mistral AI](https://mistral.ai) for the LLM and embedding APIs
- ASME standards for the reference domain
