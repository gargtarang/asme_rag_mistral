# ASME BPVC RAG + Vacuum Chamber Design Assistant

## Overview

This project provides an **offline** engineering tool with two main components:

1. **`asme_rag`**: A retrieval-augmented question-answering system over ASME BPVC PDFs
2. **`chamber`**: A deterministic design-check calculator and report generator for double-walled (jacketed), water-cooled vacuum chambers

The tool is designed to work **completely offline** with local LM Studio models (Gemma 4 26B A4B recommended) and does not require internet connectivity at runtime.

## Features

### ASME RAG System
- Parse and chunk ASME PDFs (VIII-1, VIII-2, II-D, II-A, B16.5, B36.10)
- Hybrid retrieval (SQLite FTS5 + embedding similarity)
- Grounded answer generation with citations
- Cross-reference expansion (depth limit: 1)
- Vision-based figure and table analysis (optional)
- PDF page linking in outputs

### Chamber Design System
- Rectangular or circular chamber geometry
- Double-walled (jacketed) design with water cooling
- Opening reinforcement calculations for nozzles
- Wall thickness checks under vacuum and pressure
- Flange rating checks
- Jacket rib analysis (conservative: no structural credit by default)
- FEA recommendation flag
- Check-level gating (ASK/LOOKUP values skip only dependent checks)
- Comprehensive Markdown report generation

## Quick Start

### Prerequisites
- Python 3.12
- Windows 11 Pro (or any platform with Python 3.12)
- LM Studio installed and running locally
- ASME BPVC PDFs placed in `data/pdfs/`

### Setup

1. **Clone or extract the project**:
   ```bash
   cd /path/to/project
   ```

2. **Create virtual environment and install dependencies**:
   ```bash
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```

   Or use the VS Code task: `Setup: Create venv and install dependencies`

3. **Configure LM Studio**:
   - Start LM Studio
   - Load your model (Gemma 4 26B A4B recommended)
   - Ensure the API is running at `http://localhost:1234/v1`

4. **Update configuration** (optional):
   Edit `config.toml` to customize:
   - LM Studio URL and model names
   - PDF paths
   - Retrieval parameters
   - Vision settings

5. **Place your PDFs**:
   Copy your ASME PDFs to `data/pdfs/` with the expected filenames:
   - `ASME BPVC VIII-1_2025.pdf`
   - `ASME BPVC VIII-2_2025.pdf`
   - `ASME_BPVC_IIDM_2025.pdf`
   - `ASME_BPVC_IIVI_2025.pdf`
   - `B16_5_2025.pdf`
   - `B36_10_2022.pdf`

### Usage

#### Ingest PDFs
```bash
python -m asme_rag ingest
```

This will:
- Parse all registered PDFs
- Create chunks with metadata
- Store in SQLite database
- Create embeddings (if LM Studio is available)

#### Ask Questions
```bash
# Single question
python -m asme_rag ask "What are the rules for vacuum design?"

# Interactive chat
python -m asme_rag chat
```

#### Chamber Design
```bash
# Initialize input files (interactive wizard)
python -m chamber.init

# Run calculations
python -m chamber.calc chamber.toml nozzles.toml

# Generate report
python -m chamber.report chamber.toml nozzles.toml
```

#### Other Commands
```bash
# Check system
python -m asme_rag check

# Search
python -m asme_rag search "UG-37"

# Cross-reference expansion
python -m asme_rag refs "UG-37"

# Rule map for a topic
python -m asme_rag rulemap "vacuum design"

# Materials lookup
python -m asme_rag materials "304L"

# Vision commands (if enabled)
python -m asme_rag describe-figures
python -m asme_rag figure-read
python -m asme_rag vision-test

# Provide confirmed values
python -m chamber.provide allowable_stress_SA240_304L_100C=150 --source "ASME BPVC II-D 2025 p.123"
```

## VS Code Integration

The project includes VS Code configuration:
- `.vscode/settings.json`: Python interpreter, UTF-8 console
- `.vscode/tasks.json`: Predefined tasks for all commands
- `.vscode/launch.json`: Debug configurations

Recommended extensions:
- Python
- TOML support
- Markdown preview

### Using VS Code Tasks
1. Open the project in VS Code
2. Press `Ctrl+Shift+P` and select "Tasks: Run Task"
3. Choose from available tasks:
   - `Setup: Create venv and install dependencies`
   - `RAG: Check system`
   - `RAG: Ingest PDFs`
   - `RAG: Ask`
   - `Chamber: Init`
   - `Chamber: Calc`
   - `Chamber: Report`
   - `Run Tests`

## Configuration

Edit `config.toml` to customize the system:

```toml
[lm_studio]
api_url = "http://localhost:1234/v1"
chat_model = "gemma-4-26b-a4b"
embedding_model = "nomic-ai/text-embedding-nomic-embed-text-v1.5"
temperature = 0.1

[vision]
enabled = true
render_dpi = 150
repeat_reads = 2
reading_tolerance_pct = 5.0

[retrieval]
top_k = 10
similarity_threshold = 0.7
keyword_weight = 0.4
embedding_weight = 0.6

[xref]
max_depth = 1  # Hard maximum
prompt_to_expand = true

[chamber]
structural_credit = "none"  # none / panel / fea
fea_nozzle_threshold = 5
```

## Input Files

### chamber.toml
Main chamber configuration with:
- Governing code and edition
- Geometry (rectangular or circular)
- Inner wall properties
- Jacket properties
- Load cases
- Output settings

### nozzles.toml
Nozzle configuration with:
- Nozzle dimensions and positions
- Opening details
- Jacket penetration details
- Flange defaults

### CSV Input (Optional)
For multiple nozzles, you can use `inputs/nozzles.csv` instead of `nozzles.toml`.

## Value Resolution Protocol

The system uses a ladder for missing or unresolved inputs:

1. **Drawing or design choice** (thickness, pitch, corrosion allowance, weld sizes)
   - Cannot be derived
   - List what it affects with code citations
   - Ask user to provide

2. **Code value in clean text or readable table** (joint efficiency, allowable stress)
   - Show snippet with clause and page
   - Read the value
   - Ask user to confirm

3. **Code value in chart, figure, or image-only table**
   - Print request with book, clause, figure/table number, PDF page
   - If vision enabled, show PROPOSED (unverified) reading
   - Only user-confirmed values are used

4. **Iterative values** (chart-derived factors)
   - Propose trial value
   - Ask for reading
   - Recompute and repeat until converged

## Output

### Answers
- Saved to `outputs/chat/YYYY-MM-DD_HHMM_topic.md`
- Includes: question, retrieved excerpts, answer, citations, Verify line
- Opens in VS Code if configured

### Reports
- Saved to `reports/chamber_report.md`
- Includes: document control, scope, inputs, results, verified data, warnings
- Plain Markdown for easy conversion to Word/PDF

## Testing

Run tests with:
```bash
python -m pytest tests/ -v
```

Or use the VS Code task: `Run Tests`

### Test Coverage
- PDF parsing (synthetic pages)
- Chunking and metadata
- Storage and retrieval
- Citation checking
- Cross-reference expansion
- Formula calculations (with test vectors)
- Report generation

## Fake LM Studio Server

For offline testing without LM Studio, use the fake server:
```bash
python -m tests.fake_lm_server
```

This provides mock responses for:
- Chat completions
- Embeddings
- Vision analysis

## Project Structure

```
asme_rag/
  __init__.py
  __main__.py
  cli.py          # Command-line interface
  pdf_parser.py   # PDF parsing with PyMuPDF
  chunker.py      # Text chunking
  storage.py      # SQLite storage with FTS5
  rag.py          # Retrieval and generation
  vision.py       # Vision-based analysis
  xref.py         # Cross-reference expansion
  utils.py        # Utilities and configuration

chamber/
  __init__.py
  __main__.py
  calc.py         # Main calculator
  report.py       # Report generator
  init.py         # Input wizard
  provide.py      # Value input
  formulas.py     # Formula plugins
  lookups.py      # Data lookup functions

config.toml      # Configuration
requirements.txt # Dependencies

.vscode/         # VS Code configuration
  settings.json
  tasks.json
  launch.json
  extensions.json

tests/           # Unit tests
  fake_lm_server.py
  test_*.py

data/
  pdfs/          # ASME PDFs
  verified/      # Verified data CSVs
  asme_rag.db    # SQLite database

outputs/
  chat/          # Chat outputs
  debug_images/  # Vision debug images

reports/
  chamber_report.md

docs/            # Documentation
```

## Limitations

1. **No Internet Required**: The tool works completely offline after setup
2. **Model Agnostic**: Works with any OpenAI-compatible model in LM Studio
3. **PDF Required**: All calculations require the actual ASME PDFs to be present
4. **Verification Required**: All formulas must be verified against the actual code text
5. **Conservative Defaults**: No structural credit for ribs by default

## Troubleshooting

### LM Studio Connection Issues
- Verify LM Studio is running
- Check the API URL in `config.toml`
- Ensure the model is loaded in LM Studio
- Test with: `python -m asme_rag check`

### PDF Parsing Issues
- Ensure PDFs are in the correct location
- Check PDF paths in `config.toml`
- Verify PDFs are not password-protected

### Database Issues
- Delete `data/asme_rag.db` and re-run `ingest`
- Check file permissions

### Vision Issues
- Ensure PIL is installed: `pip install Pillow`
- Check GPU memory (8GB may limit large figures)
- Reduce `render_dpi` in `config.toml`

## Documentation

- `README.md`: This file
- `docs/ARCHITECTURE.md`: System architecture and data flow
- `docs/CHANGING_THE_CODE.md`: How to modify the code
- `docs/INPUT_REFERENCE.md`: All input keys and their meanings

## License

This tool is for personal use with licensed ASME PDFs. Ensure you have the appropriate ASME licenses before using this tool.

## Version

0.1.0 - Initial development version

## Support

This is a self-contained offline tool. For issues:
1. Check the logs in `logs/asme_rag.log`
2. Review the documentation
3. Verify your ASME PDFs are accessible
4. Ensure LM Studio is running with the correct model

## Keybindings (Optional)

Add to VS Code `keybindings.json`:
```json
{
    "key": "ctrl+alt+a",
    "command": "workbench.action.tasks.runTask",
    "args": "RAG: Ask"
}
```

This allows quick access to the ask command.
