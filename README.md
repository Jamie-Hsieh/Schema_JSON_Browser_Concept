# Engineering JSON Browser

A local, read-only Streamlit browser for Jamie Schema 1.1. The updated firstpass.json and the authoritative schema are included.

## Run on Windows

Install Python 3.10 or newer. Extract the ZIP, open a terminal inside the engineering_browser folder, and run:

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py
```

## Run on macOS or Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

Open the localhost URL printed in the terminal (usually http://localhost:8501). Stop with Ctrl+C. No database, API key, or LLM is needed. Installation requires internet; the app reads local files and makes no external API calls. Streamlit usage statistics are disabled in the supplied configuration. Start from this folder to load the configuration.

## Browse

- The bundled extraction loads initially. Upload another JSON file to replace it for the current session. Upload takes precedence over the bundled-file checkbox.
- Select a part using its containment path, optionally including its children.
- Switch between Overview, Parts, Attributes, Relationships, Requirements, Issues, Missing information, and References.
- Search matches all fields, including full quotations. Combine search with a source-document filter and each view's status/category filter.
- Select a table row or use the Inspect record dropdown. Details show the full conditions, requirement text, applicability, evidence, and linked records.
- The diagram preserves direction, including nondirectional and bidirectional edges. It represents relationships, not containment.
- References remain global. Select All parts to see unallocated requirements, issues, and checklist entries. Overview counts are whole-model totals; the checklist summary follows part scope. Search/source filters apply to record views.
- Download matching entries as JSON arrays or the original full JSON from Overview. Filtered arrays are subsets, not standalone schema-conforming models.

## Validation and limits

The bundled schema validates shape and enumerations before rendering. Additional checks report duplicate IDs, missing links, containment cycles, and checklist attribute mismatches. These checks are not engineering validation. Uploaded data is not edited or written back. References to PDFs are displayed as filenames, sections, pages, and quotations; the PDFs themselves are not bundled or automatically opened.

Requirements, conditions, and unknown values remain distinct. The bundled extraction retains the unresolved MIL-P/MIL-DTL applicability and transcription limitations recorded during extraction.

## Files

- app.py — complete application and data helpers
- schema.json — supplied Jamie JSON Schema
- firstpass.json — updated extraction from this conversation
- requirements.txt — Python dependencies
- .streamlit/config.toml — theme and usage-statistics setting
- test_app.py — focused validation and application smoke tests

Run tests after installation with `python -m unittest test_app.py` (use the virtual environment Python path above).

Streamlit dataframe API reference: https://docs.streamlit.io/develop/api-reference/data/st.dataframe

Tested dependency versions: streamlit 1.63.0, pandas 2.2.3, jsonschema 4.26.0, graphviz 0.21.
