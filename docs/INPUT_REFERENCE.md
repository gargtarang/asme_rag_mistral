# Input Reference

This document describes all input keys in the ASME RAG + Chamber Design Assistant system.

## Table of Contents

1. [chamber.toml Keys](#1-chambertoml-keys)
2. [nozzles.toml Keys](#2-nozzlestoml-keys)
3. [config.toml Keys](#3-configtoml-keys)
4. [Value Types](#4-value-types)
5. [Unit Conventions](#5-unit-conventions)

---

## 1. chamber.toml Keys

### Overview

`chamber.toml` is the main configuration file for the vacuum chamber design. All keys are optional unless marked as **Required**.

### Schema Version

| Key | Type | Required | Default | Description | Who Provides | Used By |
|-----|------|----------|---------|-------------|--------------|----------|
| `schema_version` | integer | Yes | 1 | Version of the schema | System | All |

### Governing Code

| Key | Type | Required | Default | Description | Who Provides | Used By |
|-----|------|----------|---------|-------------|--------------|----------|
| `governing.code` | string | **Required** | "ASME VIII-1" | Governing code | User | All checks |
| `governing.edition` | integer | **Required** | 2025 | Edition year | User | All checks |
| `governing.route_confirmed` | boolean | No | false | Whether the rule path is confirmed | User | All checks |

### Geometry

| Key | Type | Required | Default | Description | Who Provides | Used By |
|-----|------|----------|---------|-------------|--------------|----------|
| `geometry.shape` | string | **Required** | "rectangular" | Chamber shape: "rectangular" or "circular" | User | Wall thickness, opening reinforcement |
| `geometry.inner_L` | number/string | Conditional | "ASK" | Inner length (mm) for rectangular | User | Wall thickness |
| `geometry.inner_W` | number/string | Conditional | "ASK" | Inner width (mm) for rectangular | User | Wall thickness |
| `geometry.inner_H` | number/string | Conditional | "ASK" | Inner height (mm) for rectangular | User | Wall thickness |
| `geometry.inner_ID` | number/string | Conditional | "ASK" | Inner diameter (mm) for circular | User | Wall thickness |
| `geometry.inner_length` | number/string | Conditional | "ASK" | Inner length (mm) for circular | User | Wall thickness |

**Conditional**: Required based on `shape`:
- Rectangular: `inner_L`, `inner_W`, `inner_H`
- Circular: `inner_ID`, `inner_length`

### Inner Wall

| Key | Type | Required | Default | Description | Who Provides | Used By |
|-----|------|----------|---------|-------------|--------------|----------|
| `inner_wall.thickness` | number/string | **Required** | "ASK" | Nominal thickness (mm) | User | Wall thickness check |
| `inner_wall.material_spec` | string | No | "SA-240" | Material specification | User | Allowable stress lookup |
| `inner_wall.grade` | string | No | "304L" | Material grade | User | Allowable stress lookup |
| `inner_wall.product_form` | string | No | "plate" | Product form: "plate", "sheet", "strip" | User | Allowable stress lookup |
| `inner_wall.corrosion_allowance` | number/string | No | "ASK" | Corrosion allowance (mm) | User | Wall thickness check |
| `inner_wall.joint_category` | string | No | "ASK" | Joint category from drawing | User | Joint efficiency lookup |
| `inner_wall.rt_extent` | string | No | "ASK" | RT extent: "full", "spot", "none" | User | Joint efficiency lookup |
| `inner_wall.joint_efficiency` | number/string | No | "LOOKUP" | Joint efficiency factor (0-1) | LOOKUP | Wall thickness check |
| `inner_wall.allowable_stress` | number/string | No | "LOOKUP" | Allowable stress (MPa) | LOOKUP | Wall thickness check |

### Jacket

| Key | Type | Required | Default | Description | Who Provides | Used By |
|-----|------|----------|---------|-------------|--------------|----------|
| `jacket.gap` | number/string | No | "ASK" | Gap between inner wall and jacket (mm) | User | Geometry |
| `jacket.outer_wall_thickness` | number/string | **Required** | "ASK" | Nominal thickness of jacket outer wall (mm) | User | Jacket wall thickness check |
| `jacket.outer_material_spec` | string | No | "SA-240" | Material specification for jacket | User | Allowable stress lookup |
| `jacket.outer_grade` | string | No | "304L" | Material grade for jacket | User | Allowable stress lookup |
| `jacket.outer_product_form` | string | No | "plate" | Product form for jacket | User | Allowable stress lookup |
| `jacket.outer_corrosion_allowance` | number/string | No | "ASK" | Corrosion allowance for jacket (mm) | User | Jacket wall thickness check |
| `jacket.outer_allowable_stress` | number/string | No | "LOOKUP" | Allowable stress for jacket (MPa) | LOOKUP | Jacket wall thickness check |

### Jacket Ribs

| Key | Type | Required | Default | Description | Who Provides | Used By |
|-----|------|----------|---------|-------------|--------------|----------|
| `jacket.ribs.structural_credit` | string | No | "none" | Structural credit: "none", "panel", "fea" | User | Jacket check |
| `jacket.ribs.drawing_note` | string | No | "" | Label from drawing | User | Report |
| `jacket.ribs.plug_weld_check` | boolean | No | false | Whether to check plug weld strength | User | Plug weld check |
| `jacket.ribs.thickness` | number/string | Conditional | "ASK" | Rib thickness (mm) | User | Plug weld check |
| `jacket.ribs.plug_hole_diameter` | number/string | Conditional | "ASK" | Plug hole diameter (mm) | User | Plug weld check |
| `jacket.ribs.plug_pitch_along_rib` | number/string | Conditional | "ASK" | Plug pitch along rib (mm) | User | Plug weld check |

**Conditional**: Required if `plug_weld_check = true`

### Jacket Panels (if structural_credit = "panel")

| Key | Type | Required | Default | Description | Who Provides | Used By |
|-----|------|----------|---------|-------------|--------------|----------|
| `jacket.ribs.panel.id` | string | No | "" | Panel identifier | User | Panel check |
| `jacket.ribs.panel.span_a` | number/string | Conditional | "ASK" | Longest unsupported dimension (mm) | User | Panel check |
| `jacket.ribs.panel.span_b` | number/string | Conditional | "ASK" | Other dimension (mm) | User | Panel check |

**Conditional**: Required if `structural_credit = "panel"`

### FEA (if structural_credit = "fea")

| Key | Type | Required | Default | Description | Who Provides | Used By |
|-----|------|----------|---------|-------------|--------------|----------|
| `jacket.ribs.results_csv` | string | No | "data/verified/fea_results.csv" | Path to FEA results CSV | User | FEA check |
| `jacket.ribs.acceptance_basis` | string | No | "ASK" | Code criteria for FEA results | User | FEA check |
| `jacket.ribs.software` | string | No | "" | FEA software used | User | Report |
| `jacket.ribs.model_note` | string | No | "" | Model note (element type, mesh, BCs) | User | Report |

### Stiffeners

| Key | Type | Required | Default | Description | Who Provides | Used By |
|-----|------|----------|---------|-------------|--------------|----------|
| `stiffeners.present` | boolean/string | No | "ASK" | Whether external stiffeners are present | User | Stiffener check |
| `stiffeners.pitch` | number/string | Conditional | "ASK" | Pitch between stiffeners (mm) | User | Stiffener check |
| `stiffeners.section` | string | Conditional | "ASK" | Section size (e.g., "100x10 flat bar") | User | Stiffener check |

**Conditional**: Required if `present = true`

### Load Cases

Each load case is a table entry `[[load_cases]]`.

| Key | Type | Required | Default | Description | Who Provides | Used By |
|-----|------|----------|---------|-------------|--------------|----------|
| `load_cases.name` | string | **Required** | - | Name of the load case | User | All checks |
| `load_cases.chamber_pressure` | number | **Required** | - | Chamber pressure (MPa, gauge) | User | Wall thickness, opening reinforcement |
| `load_cases.jacket_pressure` | number/string | No | "ASK" | Jacket pressure (MPa, gauge) | User | Jacket wall thickness |
| `load_cases.external_pressure` | number | No | 0.0 | External pressure (MPa, gauge) | User | Wall thickness |
| `load_cases.temperature_inner` | number/string | No | "ASK" | Inner wall temperature (°C) | User | Allowable stress lookup |
| `load_cases.temperature_jacket` | number/string | No | "ASK" | Jacket water temperature (°C) | User | Allowable stress lookup |

**Pressure Convention**: GAUGE pressure (atmosphere = 0, vacuum negative)

### Verified Data

| Key | Type | Required | Default | Description | Who Provides | Used By |
|-----|------|----------|---------|-------------|--------------|----------|
| `verified_data.allowables_csv` | string | No | "data/verified/allowables.csv" | Path to allowables CSV | User | Lookups |
| `verified_data.ext_pressure_csv` | string | No | "data/verified/ext_pressure_charts.csv" | Path to external pressure charts CSV | User | Lookups |
| `verified_data.verified_by_user` | boolean | No | false | Whether user has verified data | User | All lookups |

### Output

| Key | Type | Required | Default | Description | Who Provides | Used By |
|-----|------|----------|---------|-------------|--------------|----------|
| `output.markdown_report` | string | No | "reports/chamber_report.md" | Path to output report | User | Report generation |
| `output.cite` | boolean | No | true | Whether to include citations | User | Report generation |

---

## 2. nozzles.toml Keys

### Overview

`nozzles.toml` configures the nozzles for the chamber. Multiple nozzles can be defined with `[[nozzle]]` entries.

### Schema Version

| Key | Type | Required | Default | Description | Who Provides | Used By |
|-----|------|----------|---------|-------------|--------------|----------|
| `schema_version` | integer | Yes | 1 | Version of the schema | System | All |

### Flange Defaults

| Key | Type | Required | Default | Description | Who Provides | Used By |
|-----|------|----------|---------|-------------|--------------|----------|
| `flange_defaults.standard` | string | No | "B16.5" | Flange standard | User | Flange lookup |
| `flange_defaults.rating_class` | integer | No | 150 | Rating class | User | Flange lookup |
| `flange_defaults.material_spec` | string | No | "ASK" | Flange material specification | User | Flange lookup |
| `flange_defaults.grade` | string | No | "304L" | Flange material grade | User | Flange lookup |
| `flange_defaults.product_form` | string | No | "ASK" | Flange product form | User | Flange lookup |
| `flange_defaults.material_group` | string | No | "ASK" | B16.5 material group | User | Flange lookup |
| `flange_defaults.flange_type` | string | No | "ASK" | Flange type: "weld neck", "slip-on", "blind" | User | Flange lookup |
| `flange_defaults.facing` | string | No | "ASK" | Facing type: "RF", "FF" | User | Flange lookup |

### Spacing

| Key | Type | Required | Default | Description | Who Provides | Used By |
|-----|------|----------|---------|-------------|--------------|----------|
| `spacing.datum` | string | No | "ASK" | Datum for positioning | User | Spacing check |
| `spacing.min_edge_distance` | number/string | No | "LOOKUP" | Minimum edge distance (mm) | LOOKUP | Spacing check |
| `spacing.check_reinforcement_overlap` | boolean | No | true | Whether to check reinforcement overlap | User | Spacing check |

### Nozzle

Each nozzle is defined with `[[nozzle]]`.

| Key | Type | Required | Default | Description | Who Provides | Used By |
|-----|------|----------|---------|-------------|--------------|----------|
| `nozzle.id` | string | **Required** | - | Unique identifier | User | All checks |
| `nozzle.service` | string | No | "ASK" | Service description | User | Report |
| `nozzle.nps` | string | No | "ASK" | Nominal Pipe Size | User | Pipe lookup |
| `nozzle.schedule` | string | No | "ASK" | Pipe schedule | User | Pipe lookup |
| `nozzle.neck_od` | number/string | No | "LOOKUP" | Neck outside diameter (mm) | LOOKUP | Opening reinforcement |
| `nozzle.neck_thickness` | number/string | No | "LOOKUP" | Neck thickness (mm) | LOOKUP | Opening reinforcement |
| `nozzle.mill_undertolerance` | number/string | No | "LOOKUP" | Mill under-tolerance (%) or (mm) | LOOKUP | Thickness check |
| `nozzle.neck_material_spec` | string | No | "ASK" | Neck material specification | User | Allowable stress lookup |
| `nozzle.neck_grade` | string | No | "304L" | Neck material grade | User | Allowable stress lookup |
| `nozzle.neck_product_form` | string | No | "ASK" | Neck product form | User | Allowable stress lookup |
| `nozzle.neck_allowable_stress` | number/string | No | "LOOKUP" | Neck allowable stress (MPa) | LOOKUP | Opening reinforcement |
| `nozzle.wall` | string | No | "ASK" | Which wall: "front", "back", "left", "right", "top", "bottom", "shell", "head" | User | Positioning |
| `nozzle.x` | number/string | No | "ASK" | X position from datum (mm) | User | Positioning |
| `nozzle.y` | number/string | No | "ASK" | Y position from datum (mm) | User | Positioning |
| `nozzle.projection_outward` | number/string | No | "ASK" | Projection outward from outer jacket (mm) | User | Geometry |
| `nozzle.projection_inward` | number/string | No | "ASK" | Projection inward into chamber (mm) | User | Geometry |
| `nozzle.flange_rating_check` | boolean | No | false | Whether to check flange rating | User | Flange check |

### Nozzle Inner Wall Opening

| Key | Type | Required | Default | Description | Who Provides | Used By |
|-----|------|----------|---------|-------------|--------------|----------|
| `nozzle.inner_wall_opening.shape` | string | No | "circular" | Opening shape: "circular", "oval", "slot" | User | Opening reinforcement |
| `nozzle.inner_wall_opening.diameter` | number/string | **Required** | "ASK" | Opening diameter (mm) | User | Opening reinforcement |
| `nozzle.inner_wall_opening.neck_to_wall_weld_type` | string | No | "ASK" | Weld type between neck and inner wall | User | Opening reinforcement |
| `nozzle.inner_wall_opening.neck_to_wall_weld_size` | number/string | No | "ASK" | Weld size (mm) | User | Opening reinforcement |

### Nozzle Jacket Penetration

| Key | Type | Required | Default | Description | Who Provides | Used By |
|-----|------|----------|---------|-------------|--------------|----------|
| `nozzle.jacket_penetration.closure_type` | string | No | "ASK" | Closure type: "ring", "sleeve", "other" | User | Jacket check |
| `nozzle.jacket_penetration.opening_diameter_outer_wall` | number/string | No | "ASK" | Opening diameter in outer wall (mm) | User | Jacket check |
| `nozzle.jacket_penetration.neck_to_outer_wall_weld_type` | string | No | "ASK" | Weld type between neck and outer wall | User | Jacket check |
| `nozzle.jacket_penetration.neck_to_outer_wall_weld_size` | number/string | No | "ASK" | Weld size (mm) | User | Jacket check |

### Nozzle Pad

| Key | Type | Required | Default | Description | Who Provides | Used By |
|-----|------|----------|---------|-------------|--------------|----------|
| `nozzle.pad.present` | boolean | No | false | Whether a reinforcement pad is present | User | Opening reinforcement |
| `nozzle.pad.thickness` | number/string | Conditional | "ASK" | Pad thickness (mm) | User | Opening reinforcement |
| `nozzle.pad.outer_dimension` | number/string | Conditional | "ASK" | Pad outer dimension (mm) | User | Opening reinforcement |
| `nozzle.pad.material_spec` | string | Conditional | "ASK" | Pad material specification | User | Opening reinforcement |

**Conditional**: Required if `present = true`

### Nozzle External Loads

| Key | Type | Required | Default | Description | Who Provides | Used By |
|-----|------|----------|---------|-------------|--------------|----------|
| `nozzle.external_loads.present` | boolean | No | false | Whether external loads are applied | User | Load analysis |
| `nozzle.external_loads.note` | string | Conditional | "ASK" | Description of external loads | User | Report |

**Conditional**: Required if `present = true`

### CSV Input

Alternatively, nozzles can be provided via `inputs/nozzles.csv` with columns:

| Column | Type | Required | Description | Who Provides | Used By |
|--------|------|----------|-------------|--------------|----------|
| id | string | **Required** | Nozzle identifier | User | All |
| nps | string | No | Nominal Pipe Size | User | Pipe lookup |
| schedule | string | No | Pipe schedule | User | Pipe lookup |
| neck_od | number | No | Neck outside diameter (mm) | User/LOOKUP | Opening reinforcement |
| neck_thickness | number | No | Neck thickness (mm) | User/LOOKUP | Opening reinforcement |
| neck_material_spec | string | No | Neck material specification | User | Allowable stress lookup |
| neck_grade | string | No | Neck material grade | User | Allowable stress lookup |
| neck_product_form | string | No | Neck product form | User | Allowable stress lookup |
| wall | string | No | Which wall | User | Positioning |
| x | number | No | X position (mm) | User | Positioning |
| y | number | No | Y position (mm) | User | Positioning |
| projection_outward | number | No | Projection outward (mm) | User | Geometry |
| projection_inward | number | No | Projection inward (mm) | User | Geometry |
| inner_opening_diameter | number | **Required** | Opening diameter (mm) | User | Opening reinforcement |
| neck_to_inner_wall_weld_size | number | No | Weld size (mm) | User | Opening reinforcement |
| closure_type | string | No | Closure type | User | Jacket check |
| outer_opening_diameter | number | No | Outer opening diameter (mm) | User | Jacket check |
| neck_to_outer_wall_weld_size | number | No | Weld size (mm) | User | Jacket check |
| pad_present | boolean | No | Whether pad is present | User | Opening reinforcement |
| pad_thickness | number | No | Pad thickness (mm) | User | Opening reinforcement |
| pad_outer_dimension | number | No | Pad outer dimension (mm) | User | Opening reinforcement |

---

## 3. config.toml Keys

### Overview

`config.toml` contains all tunable parameters for the system. All keys are optional with sensible defaults.

### General Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `general.project_name` | string | "ASME BPVC RAG + Vacuum Chamber Design Assistant" | Project name |
| `general.workspace_root` | string | "." | Workspace root directory |
| `general.force_utf8` | boolean | true | Force UTF-8 console on Windows |

### LM Studio Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `lm_studio.api_url` | string | "http://localhost:1234/v1" | LM Studio API endpoint |
| `lm_studio.chat_model` | string | "gemma-4-26b-a4b" | Chat model name |
| `lm_studio.embedding_model` | string | "nomic-ai/text-embedding-nomic-embed-text-v1.5" | Embedding model name |
| `lm_studio.query_prefix` | string | "search_query: " | Prefix for query embeddings |
| `lm_studio.chunk_prefix` | string | "search_document: " | Prefix for chunk embeddings |
| `lm_studio.temperature` | float | 0.1 | Generation temperature |
| `lm_studio.max_tokens` | integer | 4096 | Maximum tokens for response |
| `lm_studio.timeout_seconds` | integer | 120 | Timeout for API calls |

### Vision Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `vision.enabled` | boolean | true | Enable vision analysis |
| `vision.model` | string | "gemma-4-26b-a4b" | Vision model name |
| `vision.render_dpi` | integer | 150 | DPI for figure rendering |
| `vision.max_image_px` | integer | 2048 | Maximum image dimension |
| `vision.max_figures_per_run` | integer | 10 | Maximum figures to process at once |
| `vision.timeout_s` | integer | 60 | Timeout for vision requests |
| `vision.save_page_images` | boolean | false | Save debug images to disk |
| `vision.debug_dir` | string | "outputs/debug_images" | Debug image directory |
| `vision.repeat_reads` | integer | 2 | Number of repeat reads for stability |
| `vision.reading_tolerance_pct` | float | 5.0 | Tolerance for stable readings (%) |
| `vision.resume` | boolean | true | Resume from previous figures |

### PDF Parser Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `pdf_parser.strip_patterns` | list | Copyright patterns | Regex patterns to strip from text |
| `pdf_parser.header_footer_threshold` | float | 0.1 | Page fraction for header/footer detection |
| `pdf_parser.min_text_height` | integer | 6 | Minimum text height (points) |
| `pdf_parser.column_gap_threshold` | integer | 20 | Gap threshold for column detection |
| `pdf_parser.min_column_width` | integer | 100 | Minimum column width |

### Chunker Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `chunker.target_chunk_size` | integer | 1024 | Target chunk size (characters) |
| `chunker.min_chunk_size` | integer | 256 | Minimum chunk size |
| `chunker.max_chunk_size` | integer | 4096 | Maximum chunk size |
| `chunker.chunk_overlap` | integer | 256 | Overlap between chunks |
| `chunker.clause_patterns` | list | ASME patterns | Regex patterns for clause detection |
| `chunker.table_patterns` | list | Table patterns | Regex patterns for table detection |
| `chunker.figure_patterns` | list | Figure patterns | Regex patterns for figure detection |
| `chunker.xref_patterns` | list | Cross-reference patterns | Regex patterns for reference detection |

### Documents Registry

Each document is a `[[documents]]` table with:

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `id` | string | **Required** | - | Unique document identifier |
| `code` | string | **Required** | - | Code name (e.g., "ASME BPVC") |
| `division` | string | No | "" | Division (e.g., "VIII-1") |
| `edition` | integer | **Required** | - | Edition year |
| `unit_system` | string | No | "mixed" | Unit system: "mixed", "metric", "us" |
| `pdf_path` | string | **Required** | - | Path to PDF file |
| `parser_profile` | string | No | "code_book" | Parser profile |
| `chunker_profile` | string | No | "code_book" | Chunker profile |

### Storage Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `storage.database_path` | string | "data/asme_rag.db" | SQLite database path |
| `storage.fts5_tokenize` | string | "unicode61 remove_diacritics 2" | FTS5 tokenization settings |

### Retrieval Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `retrieval.top_k` | integer | 10 | Number of top results |
| `retrieval.similarity_threshold` | float | 0.7 | Minimum similarity for embedding search |
| `retrieval.keyword_weight` | float | 0.4 | Weight for keyword search |
| `retrieval.embedding_weight` | float | 0.6 | Weight for embedding search |
| `retrieval.min_score` | float | 0.5 | Minimum combined score |

### Embedding Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `embedding.embedding_dim` | integer | 768 | Embedding dimension |
| `embedding.batch_size` | integer | 32 | Batch size for embedding |

### Cross-Reference Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `xref.max_depth` | integer | 1 | Maximum expansion depth (HARD MAXIMUM) |
| `xref.max_clauses` | integer | 40 | Maximum clauses to collect |
| `xref.ask_when_larger_than` | integer | 40 | Ask before expanding more than this |
| `xref.include_footnotes` | boolean | true | Include footnotes in expansion |
| `xref.show_unexpanded` | boolean | true | Show further references |
| `xref.write_pack_file` | boolean | true | Write reference pack to file |
| `xref.prompt_to_expand` | boolean | true | Prompt to expand further references |

### Links Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `links.pdf_page_links` | boolean | true | Enable PDF page links |
| `links.pdf_base_dir` | string | "data/pdfs" | Base directory for PDFs |
| `links.anchor_style` | string | "#page={n}" | Anchor style for PDF links |

### Serve Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `serve.host` | string | "127.0.0.1" | Web server host |
| `serve.port` | integer | 8765 | Web server port |

### Output Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `output.open_in_vscode` | boolean | true | Open outputs in VS Code |
| `output.chat_history_max` | integer | 3 | Maximum chat history items |

### Chamber Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `chamber.default_code` | string | "ASME VIII-1" | Default governing code |
| `chamber.default_edition` | integer | 2025 | Default edition |
| `chamber.structural_credit` | string | "none" | Default structural credit |
| `chamber.fea_nozzle_threshold` | integer | 5 | Nozzle count for FEA recommendation |

### Evaluation Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `eval.models` | list | ["gemma-4-26b-a4b"] | Models to evaluate |
| `eval.eval_questions_file` | string | "tests/eval_questions.toml" | Evaluation questions file |

### Logging Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `logging.level` | string | "INFO" | Log level |
| `logging.log_file` | string | "logs/asme_rag.log" | Log file path |
| `logging.console_log` | boolean | true | Enable console logging |

---

## 4. Value Types

### Special Values

| Value | Type | Meaning | Behavior |
|-------|------|---------|----------|
| `ASK` | string | User must provide | Check is skipped, listed in NEEDS INPUT |
| `LOOKUP` | string | Look up from code | System attempts lookup, user must confirm |
| `""` (empty) | string | Not provided | Treated as ASK |
| `None` | null | Not present | Treated as ASK |

### Numeric Types

| Type | Example | Description |
|------|---------|-------------|
| integer | `150` | Whole number |
| float | `150.5` | Decimal number |
| string number | `"150.5"` | Number as string (converted automatically) |

### Boolean Types

| Value | Meaning |
|-------|---------|
| `true` | True |
| `false` | False |
| `"true"` | True |
| `"false"` | False |
| `1` | True |
| `0` | False |

---

## 5. Unit Conventions

### Base Units

| Quantity | Unit | Notes |
|----------|------|-------|
| Length | mm | Millimeters |
| Pressure | MPa | Megapascals (gauge) |
| Temperature | °C | Degrees Celsius |
| Stress | MPa | Megapascals |
| Force | N | Newtons |

### Pressure Convention

- **GAUGE pressure**: Atmosphere = 0
- **Vacuum**: Negative gauge pressure
  - Full vacuum: -0.101 MPa (approximately)
  - Partial vacuum: -0.05 MPa, etc.
- **Internal pressure**: Positive gauge pressure
- **Net load**: Pressure difference across a wall

### Example Conversions

| From | To | Factor |
|------|---|--------|
| MPa | psi | 145.038 |
| MPa | bar | 10 |
| MPa | kgf/cm² | 10.1972 |
| mm | inch | 0.0393701 |
| °C | °F | (°C × 9/5) + 32 |

### Notes

- All inputs and outputs must specify units
- The system does NOT perform unit conversions automatically
- All calculations are in SI-mm units (mm, MPa, degC, N)
- Flange standards (B16.5) may use US customary units - the system states which table set was used

---

## Summary

This document provides a complete reference for all input keys in the ASME RAG + Chamber Design Assistant system. For more information on how to use these keys, see:

- `README.md` - General usage
- `docs/ARCHITECTURE.md` - System architecture
- `docs/CHANGING_THE_CODE.md` - How to modify the code
