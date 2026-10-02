# PennyPilot AI — Upgraded MVP v2

This version keeps the existing Streamlit MVP architecture and adds:

- Fixed optional Groq AI integration using a currently documented model default: `openai/gpt-oss-20b`.
- Visible AI error messages instead of silently hiding API failures.
- A much more data-driven Money Coach using budget pace, top categories, essential/discretionary spending, largest transaction, and savings goals.
- Stronger receipt OCR preprocessing: enlargement, contrast enhancement, sharpening, thresholding, and multiple Tesseract passes.
- Better receipt total detection using total/amount-due labels while penalizing subtotal/tax/change lines.
- Delete one or multiple expenses from the Dashboard.
- Bulk CSV, XLSX, and XLS import with column-name mapping, validation, preview/editing, category suggestions, and confirmation before import.
- Transaction IDs internally so deletion is reliable.

## Streamlit Secrets

If you want the optional AI explanation, add:

```toml
GROQ_API_KEY = "your_key_here"
GROQ_MODEL = "openai/gpt-oss-20b"
```

Do not put the key in GitHub or in `app.py`.

## Bulk spreadsheet format

Recommended columns:

`Date | Merchant | Description | Category | Amount | Currency`

`Category` and `Currency` can be omitted. PennyPilot will suggest a category and use the selected budget currency.

## Deployment

Upload the project files to GitHub and deploy `app.py` through Streamlit Community Cloud. No local Python testing is required for this workflow.

The app remains session-only; a production version should add authenticated persistent storage.
