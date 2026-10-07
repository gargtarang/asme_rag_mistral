# Changing the ASME RAG + Chamber Design Assistant Code

This document provides step-by-step recipes for common modifications to the codebase.

## Table of Contents

1. [Adding a New Book or Edition](#1-adding-a-new-book-or-edition)
2. [Changing Clause-ID Regexes](#2-changing-clause-id-regexes)
3. [Adding a New Check](#3-adding-a-new-check)
4. [Adding or Renaming TOML/CSV Keys](#4-adding-or-renaming-tomlcsv-keys)
5. [Switching the Chat Model](#5-switching-the-chat-model)
6. [Changing Thresholds](#6-changing-thresholds)
7. [Changing Cross-Reference Limits](#7-changing-cross-reference-limits)
8. [Changing PDF Link Style](#8-changing-pdf-link-style)
9. [Adding Vision Test Cases](#9-adding-vision-test-cases)
10. [Adding a New Formula Plugin](#10-adding-a-new-formula-plugin)
11. [Adding a New Lookup Function](#11-adding-a-new-lookup-function)
12. [Changing Chunking Parameters](#12-changing-chunking-parameters)
13. [Adding a New Document Profile](#13-adding-a-new-document-profile)

---

## 1. Adding a New Book or Edition

To add a new ASME book or edition to the system:

### Steps

1. **Add to config.toml**:
   ```toml
   [[documents]]
   id = "new_book_2025"
   code = "ASME New Book"
   division = "NEW"
   edition = 2025
   unit_system = "mixed"
   pdf_path = "data/pdfs/New_Book_2025.pdf"
   parser_profile = "code_book"
   chunker_profile = "code_book"
   ```

2. **Place the PDF**:
   - Copy the PDF to `data/pdfs/`
   - Ensure the filename matches the `pdf_path` in config.toml

3. **Update clause-ID regexes** (if needed):
   - Edit `clause_patterns` in `[chunker]` section of config.toml
   - Add patterns specific to the new book

4. **Test**:
   ```bash
   python -m asme_rag check
   python -m asme_rag ingest
   ```

### Files to Modify
- `config.toml` - Add document registration
- `data/pdfs/` - Add PDF file

### Verification
- Run `python -m asme_rag check` to verify PDF is found
- Run `python -m asme_rag ingest` to parse and chunk
- Check `outputs/chat/` for any errors

---

## 2. Changing Clause-ID Regexes

To modify the patterns used to detect clause IDs in text:

### Steps

1. **Edit config.toml**:
   ```toml
   [chunker]
   clause_patterns = [
       "UG-\\d+",
       "UW-\\d+",
       "NEW-\\d+",  # Add new pattern
       "Appendix\\s+\\d+",
   ]
   ```

2. **Test the patterns**:
   ```python
   import re
   patterns = [re.compile(p, re.IGNORECASE) for p in clause_patterns]
   test_text = "NEW-123 Some text"
   for pattern in patterns:
       if pattern.search(test_text):
           print(f"Matched: {pattern.pattern}")
   ```

3. **Re-ingest PDFs** (if patterns changed significantly):
   ```bash
   rm data/asme_rag.db
   python -m asme_rag ingest
   ```

### Files to Modify
- `config.toml` - clause_patterns in [chunker] section
- `asme_rag/chunker.py` - (optional) Add custom pattern handling

### EDIT HERE Markers
- In `asme_rag/chunker.py`: Look for clause_patterns initialization

---

## 3. Adding a New Check

To add a new design check to the chamber calculator:

### Steps

1. **Add formula plugin** (if needed):
   - See [Adding a New Formula Plugin](#10-adding-a-new-formula-plugin)

2. **Add check to calc.py**:
   ```python
   def check_new_feature(self, code: str, edition: int, 
                         route_confirmed: bool) -> CheckResult:
       """
       Check new feature.
       
       # VERIFY_AGAINST_PDF: This check needs verification
       """
       # Get inputs
       required_input = self.chamber_config.get('new_feature', {}).get('value')
       
       if required_input in ['ASK', 'LOOKUP', None, '']:
           return CheckResult(
               check_name="New feature check",
               passes=False,
               skipped=True,
               skip_reason="Missing inputs",
               needs_input=["New feature check requires: value"]
           )
       
       # Calculate
       # ...
       
       return CheckResult(
           check_name="New feature check",
           passes=True,
           required=required_value,
           provided=provided_value,
           unit="mm",
           clause="NEW-CLAUSE (VERIFY_AGAINST_PDF)",
           code=code,
           edition=edition
       )
   ```

3. **Call the check in run_checks()**:
   ```python
   def run_checks(self) -> List[CheckResult]:
       # ... existing checks ...
       
       # New check
       if self.has_required_inputs(['new_feature.value']):
           result = self.check_new_feature(code, edition, route_confirmed)
           self.check_results.append(result)
       else:
           self.not_checked.append("New feature check (missing inputs)")
   ```

4. **Add to input wizard** (optional):
   - Edit `chamber/init.py` to add input fields

### Files to Modify
- `chamber/calc.py` - Add check method and call in run_checks()
- `chamber/formulas.py` - (optional) Add formula plugin
- `chamber/init.py` - (optional) Add to input wizard

### Verification
- Test with: `python -m chamber.calc chamber.toml nozzles.toml`
- Verify check appears in results

---

## 4. Adding or Renaming TOML/CSV Keys

To add or rename a key in chamber.toml or nozzles.toml:

### Steps for Adding

1. **Add to schema** in documentation:
   - Update `docs/INPUT_REFERENCE.md`

2. **Add to default config** in init.py:
   ```python
   def get_default_chamber_config(self) -> Dict[str, Any]:
       return {
           # ... existing keys ...
           'new_key': 'ASK',  # or default value
       }
   ```

3. **Update loader** in calc.py:
   ```python
   def load_chamber_config(self, config_path: str) -> bool:
       # ... existing loading ...
       self.new_key = self.chamber_config.get('new_key', 'ASK')
   ```

4. **Update checks** that use the key:
   - Search for references to the old key
   - Update to use the new key

### Steps for Renaming

1. **Update all references**:
   ```bash
   grep -r "old_key" chamber/ asme_rag/
   ```

2. **Update default config**:
   ```python
   # Change in init.py
   'new_key': config.get('old_key', 'ASK')
   ```

3. **Update tests**:
   - Update test files that reference the old key

### Files to Modify
- `chamber/init.py` - Default config and input wizard
- `chamber/calc.py` - Loading and usage
- `tests/test_chamber.py` - (if exists) Update tests
- `docs/INPUT_REFERENCE.md` - Documentation

### Verification
- Run `python -m chamber.init` to verify wizard works
- Run `python -m chamber.calc chamber.toml nozzles.toml` to verify loading

---

## 5. Switching the Chat Model

To change the chat model used for generation:

### Steps

1. **Edit config.toml**:
   ```toml
   [lm_studio]
   chat_model = "new-model-name"
   ```

2. **Verify model is available**:
   - Start LM Studio
   - Load the new model
   - Check with: `python -m asme_rag check`

3. **Test**:
   ```bash
   python -m asme_rag ask "Test question"
   ```

### Files to Modify
- `config.toml` - chat_model in [lm_studio] section

### Verification
- Run `python -m asme_rag check` to verify model is available
- Run `python -m asme_rag ask` to test generation

---

## 6. Changing Thresholds

To change various thresholds (similarity, scores, etc.):

### Steps

1. **Edit config.toml**:
   ```toml
   [retrieval]
   top_k = 15  # Return more results
   similarity_threshold = 0.8  # Higher threshold
   keyword_weight = 0.3
   embedding_weight = 0.7
   min_score = 0.6
   ```

2. **Test**:
   ```bash
   python -m asme_rag search "test query"
   ```

### Common Thresholds

| Section | Parameter | Purpose |
|---------|-----------|---------|
| [retrieval] | top_k | Number of results to return |
| [retrieval] | similarity_threshold | Minimum similarity for embedding search |
| [retrieval] | keyword_weight | Weight for keyword search in hybrid |
| [retrieval] | embedding_weight | Weight for embedding search in hybrid |
| [retrieval] | min_score | Minimum combined score for a result |
| [chunker] | target_chunk_size | Target size for chunks |
| [chunker] | min_chunk_size | Minimum chunk size |
| [chunker] | max_chunk_size | Maximum chunk size |
| [vision] | reading_tolerance_pct | Tolerance for stable vision readings |
| [chamber] | fea_nozzle_threshold | Nozzle count for FEA recommendation |

### Files to Modify
- `config.toml` - Various sections

### Verification
- Run appropriate commands to test changes

---

## 7. Changing Cross-Reference Limits

To change cross-reference expansion limits:

### Steps

1. **Edit config.toml**:
   ```toml
   [xref]
   max_depth = 1  # HARD MAXIMUM - cannot be changed
   max_clauses = 50  # Maximum clauses to collect
   ask_when_larger_than = 30  # Ask before expanding more than this
   include_footnotes = true
   show_unexpanded = true
   write_pack_file = true
   prompt_to_expand = true
   ```

2. **Note**: The hard maximum depth is 1 (as per requirements)
   - This is enforced in `asme_rag/utils.py` with `MAX_XREF_DEPTH = 1`
   - Do NOT change this constant

3. **Test**:
   ```bash
   python -m asme_rag refs "UG-37"
   ```

### Files to Modify
- `config.toml` - [xref] section
- `asme_rag/utils.py` - (do NOT change MAX_XREF_DEPTH)
- `asme_rag/xref.py` - (optional) Custom behavior

### EDIT HERE Markers
- In `asme_rag/utils.py`: `MAX_XREF_DEPTH = 1` (do NOT change)
- In `asme_rag/xref.py`: max_depth handling

---

## 8. Changing PDF Link Style

To change how PDF page links are generated in outputs:

### Steps

1. **Edit config.toml**:
   ```toml
   [links]
   pdf_page_links = true
   pdf_base_dir = "data/pdfs"
   anchor_style = "#page={n}"  # Change this
   ```

2. **Common anchor styles**:
   - `#page={n}` - Standard (works with most viewers)
   - `#page={n}&view=FitH` - Fit horizontally
   - `#nameddest={n}` - Named destination (if defined in PDF)

3. **Test**:
   ```bash
   python -m asme_rag ask "Test question"
   ```
   - Check the generated Markdown file for links

### Files to Modify
- `config.toml` - [links] section
- `asme_rag/utils.py` - (optional) Custom link generation

### Verification
- Run a question that generates citations
- Check the output Markdown for proper links

---

## 9. Adding Vision Test Cases

To add test cases for vision analysis:

### Steps

1. **Create tests/vision_cases.toml**:
   ```toml
   [[test_cases]]
   name = "test_figure_1"
   doc = "viii1_2025"
   page = 123
   bbox = [100, 200, 400, 500]
   prompt = "Describe this figure"
   expected_value = "pressure-volume chart"
   tolerance = 5.0
   
   [[test_cases]]
   name = "test_chart_reading"
   doc = "iid_metric_2025"
   page = 456
   type = "value"
   prompt = "Read the value for SA-240 at 100C"
   expected_value = 150
   unit = "MPa"
   tolerance = 1.0
   ```

2. **Run vision tests**:
   ```bash
   python -m asme_rag vision-test
   ```

### Files to Modify
- `tests/vision_cases.toml` - Add test cases
- `asme_rag/vision.py` - (optional) Custom test handling

### Verification
- Run `python -m asme_rag vision-test`
- Check output for test results

---

## 10. Adding a New Formula Plugin

To add a new formula for a specific code rule:

### Steps

1. **Create formula class** in formulas.py:
   ```python
   class NewFormula(FormulaPlugin):
       """
       Formula for new calculation.
       
       # VERIFY_AGAINST_PDF: This formula needs verification
       """
       
       def __init__(self, code: str = "ASME VIII-1", 
                    edition: int = 2025, clause: str = "NEW-CLAUSE"):
           super().__init__(code, edition, clause)
       
       def calculate(self, inputs: Dict[str, Any]) -> FormulaResult:
           # Get inputs
           param1 = inputs.get('param1', 0)
           param2 = inputs.get('param2', 0)
           
           # VERIFY_AGAINST_PDF: Formula implementation
           # result = param1 * param2 / some_factor
           
           if param1 > 0 and param2 > 0:
               result_value = param1 * param2  # Placeholder
               
               return FormulaResult(
                   value=result_value,
                   unit="mm",
                   clause=self.clause,
                   code=self.code,
                   edition=self.edition,
                   description="Description of calculation",
                   inputs=inputs,
                   passes=False,
                   notes="VERIFY_AGAINST_PDF: Formula needs confirmation"
               )
           else:
               return FormulaResult(
                   value=0,
                   unit="mm",
                   clause=self.clause,
                   code=self.code,
                   edition=self.edition,
                   description="Description",
                   inputs=inputs,
                   passes=False,
                   notes="NEEDS INPUT: Missing required inputs"
               )
   ```

2. **Register formula** in FormulaManager:
   ```python
   class FormulaManager:
       def __init__(self, config: Optional[Dict[str, Any]] = None):
           # ... existing formulas ...
           self.formulas = {
               # ... existing ...
               'new_calculation': {
                   'ASME VIII-1': {
                       2025: NewFormula("ASME VIII-1", 2025, "NEW-CLAUSE")
                   }
               }
           }
   ```

3. **Use formula** in calc.py:
   ```python
   def check_new_feature(self, code: str, edition: int, 
                         route_confirmed: bool) -> CheckResult:
       inputs = {
           'param1': value1,
           'param2': value2,
       }
       
       result = self.formula_manager.calculate(
           'new_calculation', code, edition, inputs
       )
       
       if result:
           return CheckResult(
               check_name="New feature",
               passes=result.value < limit,
               required=result.value,
               provided=limit,
               unit=result.unit,
               clause=result.clause,
               code=result.code,
               edition=result.edition,
               formula_result=result
           )
   ```

### Files to Modify
- `chamber/formulas.py` - Add formula class and register in FormulaManager
- `chamber/calc.py` - Use formula in checks

### Verification
- Test with: `python -m chamber.calc chamber.toml nozzles.toml`
- Verify formula is used and results are correct

---

## 11. Adding a New Lookup Function

To add a new lookup function for data retrieval:

### Steps

1. **Add lookup method** in lookups.py:
   ```python
   def new_lookup(self, param1: str, param2: str) -> List[LookupResult]:
       """
       Look up new data.
       
       Returns CANDIDATE values with citations.
       """
       results = []
       
       # Search for data
       query = f"{param1} {param2}"
       filters = {'division': 'II-D'}  # or appropriate filter
       chunks = self.storage.search_chunks(query, filters)
       
       for chunk in chunks:
           # Extract data from chunk
           value = self.extract_new_data(chunk.get('text', ''))
           
           if value is not None:
               result = LookupResult(
                   value=value,
                   citation=f"[{chunk.get('code')}, {chunk.get('edition')}, "
                           f"{chunk.get('clause_id')}, PDF p.{chunk.get('pdf_page')}]",
                   source=f"{chunk.get('code')} {chunk.get('division')}",
                   pdf_page=chunk.get('pdf_page', 0),
                   table_number=chunk.get('clause_id', ''),
                   verified=False,
                   candidate=True
               )
               results.append(result)
       
       if not results:
           result = LookupResult(
               value=None,
               citation="",
               source="",
               pdf_page=0,
               table_notes=f"NEEDS INPUT: Data not found for {param1} {param2}",
               verified=False,
               candidate=False
           )
           results.append(result)
       
       return results
   ```

2. **Add to Lookups class**:
   ```python
   class Lookups:
       def __init__(self, config: Optional[Config] = None, 
                    storage: Optional[Storage] = None):
           # ... existing ...
           self.new_lookup = self.new_lookup
   ```

3. **Use lookup** in calc.py or elsewhere:
   ```python
   results = self.lookups.new_lookup(param1, param2)
   ```

### Files to Modify
- `chamber/lookups.py` - Add lookup method
- `chamber/calc.py` - (optional) Use lookup in checks

### Verification
- Test the lookup directly
- Verify results are correct

---

## 12. Changing Chunking Parameters

To change how text is chunked:

### Steps

1. **Edit config.toml**:
   ```toml
   [chunker]
   target_chunk_size = 2048  # Larger chunks
   min_chunk_size = 512
   max_chunk_size = 8192
   chunk_overlap = 512
   ```

2. **Or edit chunker.py** for profile-specific parameters:
   ```python
   self.profile_configs = {
       'code_book': {
           'chunk_size': 2048,
           'min_chunk_size': 512,
           'max_chunk_size': 8192,
           'overlap': 512,
           'split_at_clauses': True
       },
       # ... other profiles
   }
   ```

3. **Re-ingest PDFs**:
   ```bash
   rm data/asme_rag.db
   python -m asme_rag ingest
   ```

### Files to Modify
- `config.toml` - [chunker] section
- `asme_rag/chunker.py` - profile_configs

### Verification
- Run `python -m asme_rag ingest`
- Check chunk sizes with `python -m asme_rag inspect`

---

## 13. Adding a New Document Profile

To add a new document profile for specialized parsing/chunking:

### Steps

1. **Add profile to chunker.py**:
   ```python
   self.profile_configs = {
       # ... existing profiles ...
       'new_profile': {
           'chunk_size': 2048,
           'min_chunk_size': 512,
           'max_chunk_size': 8192,
           'overlap': 256,
           'split_at_clauses': False,
           'table_centric': True  # For table-heavy documents
       }
   }
   ```

2. **Update config.toml** for documents using this profile:
   ```toml
   [[documents]]
   id = "new_doc_2025"
   code = "New Standard"
   division = "NEW"
   edition = 2025
   pdf_path = "data/pdfs/New_Standard_2025.pdf"
   parser_profile = "code_book"
   chunker_profile = "new_profile"
   ```

3. **Re-ingest PDFs**:
   ```bash
   python -m asme_rag ingest
   ```

### Files to Modify
- `asme_rag/chunker.py` - Add profile to profile_configs
- `config.toml` - Set chunker_profile for documents

### Verification
- Run `python -m asme_rag ingest`
- Verify chunks are created with the new profile

---

## General Tips

### Finding EDIT HERE Markers

Search for `# EDIT HERE:` in the codebase to find common change points:
```bash
grep -r "EDIT HERE" asme_rag/ chamber/
```

### Testing Changes

Always test changes with:
1. `python -m asme_rag check` - Verify system configuration
2. `python -m asme_rag ingest` - Test PDF parsing
3. `python -m asme_rag search "test"` - Test retrieval
4. `python -m chamber.calc chamber.toml nozzles.toml` - Test calculations

### Logging

Check `logs/asme_rag.log` for detailed error information.

### Backing Up

Before making significant changes:
```bash
# Backup database
cp data/asme_rag.db data/asme_rag.db.backup

# Backup configuration
cp config.toml config.toml.backup
```

### Restoring

To start fresh:
```bash
rm -rf data/asme_rag.db data/verified/*.csv outputs/
```

---

## Support

For issues with modifications:
1. Check the logs
2. Review the documentation
3. Verify configuration changes
4. Test with small changes first
5. Check the fake LM server for offline testing
