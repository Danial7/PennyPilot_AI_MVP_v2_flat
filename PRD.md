# PennyPilot AI — Product Requirements Document (PRD)

**Version:** 1.0  
**Prepared:** 2 October 2026  
**Project type:** Hackathon MVP  
**Target deployment:** Streamlit Community Cloud  
**Development:** Python and GitHub  
**Working title:** PennyPilot AI — Smart Personal Finance Assistant

## 1. Executive Summary

PennyPilot AI is a lightweight personal finance assistant that helps users record everyday expenses, understand spending patterns, plan savings goals, and receive practical budget guidance. Users can set an approximate monthly budget in a supported currency, enter expenses manually, or upload/capture a receipt image for OCR-assisted extraction. The app categorizes expenses, presents transaction tables and category charts, and estimates the time needed to reach a savings goal.

The MVP follows a resilient, modular workflow: receipt OCR, categorization, budgeting, savings projections, country lookup, currency conversion, and optional AI explanations are independent functions. A failure in an optional service must not prevent core bookkeeping features from working.

## 2. Problem Statement

Many people do not have a simple, low-cost way to track day-to-day spending and connect it to their monthly budget and savings goals. Manual recordkeeping is time-consuming, receipts are easy to lose, and users may struggle to identify the categories consuming most of their budget.

## 3. Product Vision

Provide an accessible, transparent, currency-aware finance companion that helps users make informed spending decisions without requiring paid subscriptions or sharing financial credentials.

## 4. Target Users

- Individuals who want to track household or personal spending.
- Users who receive paper receipts or digital receipt screenshots.
- People saving for a specific purchase or goal.
- Hackathon evaluators looking for an end-to-end AI-assisted workflow built with free/low-cost tooling.

## 5. Goals and Success Criteria

1. A user can set a monthly budget and select a supported currency.
2. A user can add an expense manually.
3. A user can upload or capture a receipt image, review OCR output, correct the amount/category, and save the transaction.
4. Transactions appear in a table and category pie chart.
5. A user can create a savings goal and view an estimated timeline based on a planned monthly contribution.
6. The money coach summarizes budget use and provides practical, cautious guidance.
7. The app remains usable when OCR, country lookup, currency conversion, or optional LLM service fails.
8. No API key or secret is committed to GitHub.

## 6. Scope

### In scope for MVP

- Streamlit single-page web app with tabs.
- Monthly budget and currency selection.
- Best-effort country detection with manual override.
- Manual expense entry.
- Receipt image upload and camera capture where supported by the browser.
- OCR-assisted text extraction with user review before saving.
- Rule-based expense categorization with manual correction.
- Dashboard metrics, category pie chart, transaction table, CSV export.
- Savings goals and simple monthly-contribution timeline estimates.
- Rules-based budget coach and educational information about stocks, crypto, gold, emergency savings, and diversification.
- Optional Groq-compatible LLM explanation via Streamlit Secrets; app continues without it.
- Graceful error handling for external services.

### Out of scope for hackathon MVP

- Bank account linking or automatic bank-feed ingestion.
- Payment initiation, brokerage integration, or trading.
- Guaranteed investment returns or buy/sell recommendations for specific assets.
- User authentication, multi-device synchronization, and permanent database persistence.
- Tax, legal, or regulated investment advice.
- Guaranteed OCR accuracy across all receipt formats and languages.
- Live stock, crypto, or gold prices and real-time economic analysis.
- Automatic financial suitability assessment.

## 7. Functional Requirements

### FR-01: Budget and currency
The user can enter an approximate monthly budget and select a currency. The UI displays budget, recorded expenses, and remaining amount in that currency. Transactions are not silently combined across currencies.

### FR-02: Country context
The app may attempt best-effort country detection using an IP-based lookup. The user can override the result. If the lookup fails or returns an unsupported country, the app continues with a manual selection.

### FR-03: Expense entry
The user can manually enter date, merchant/payee, description, amount, and category. Invalid or non-positive amounts must not be saved.

### FR-04: Receipt capture and OCR
The user can upload an image or use camera capture when available. OCR extracts text; the app attempts to infer a merchant and total amount. The user must review and correct the extracted values before saving. OCR failure must not stop other features.

### FR-05: Categorization
The app suggests categories such as Groceries, Dining Out, Housing, Utilities, Transport, Education, Healthcare, Shopping, Entertainment, Personal Care, Debt Payment, and Other. The user can override the suggested category.

### FR-06: Dashboard and reporting
The dashboard shows monthly budget, recorded spending, remaining budget, budget utilization, category pie chart, and transaction table. Users can export records as CSV.

### FR-07: Savings goals
The user can define a goal name, target amount, amount already saved, and planned monthly contribution. The app estimates months to target without assuming investment growth or interest.

### FR-08: Money coach
The app gives rule-based suggestions based on budget utilization and recorded categories. It should explicitly identify that records may be incomplete.

### FR-09: Investment education
The app explains general risks and considerations for emergency savings, stocks/funds, gold, and crypto. It must not guarantee returns or present itself as a licensed advisor.

### FR-10: Optional LLM
If a Groq-compatible API key is configured in Streamlit Secrets, the app may generate a concise explanation. If missing, rate-limited, or unavailable, a warning is shown and rules-based advice remains available.

### FR-11: Export and clearing
Users can export transaction data to CSV and clear session data. The interface explains that this MVP uses session-scoped storage.

## 8. Non-Functional Requirements

- **Cost:** Core features must not require paid APIs. Optional services must be disabled gracefully when not configured.
- **Security:** Secrets must not be hardcoded or committed. Do not request bank passwords, card numbers, or credentials.
- **Reliability:** Optional features fail independently; errors should be actionable and non-fatal.
- **Usability:** Clear labels, editable OCR output, manual alternatives, and visible status messages.
- **Transparency:** Distinguish user-entered facts, estimates, OCR guesses, and general education.
- **Deployment:** Compatible with Streamlit Community Cloud using `requirements.txt` and `packages.txt`.
- **Privacy:** Explain that the MVP does not provide accounts or durable private storage. Users should avoid entering highly sensitive data.

## 9. Proposed Architecture

1. **Streamlit UI layer:** profile, budget, forms, dashboard, goals, coach, exports.
2. **Receipt extraction component:** image decoding and Tesseract OCR; errors are caught and surfaced.
3. **Categorization component:** keyword rules that provide an editable category suggestion.
4. **Transaction component:** session-scoped transaction table with validation.
5. **Budget analysis component:** totals, category aggregates, budget utilization, and actionable rules.
6. **Goal planner:** arithmetic estimate using target, current savings, and monthly contribution.
7. **Country context component:** optional no-key IP lookup plus manual override.
8. **Currency conversion utility:** optional public exchange-rate endpoint; unsupported pairs fall back without conversion.
9. **Optional AI explanation:** external LLM call only when a secret is configured; otherwise rules-based output.
10. **Presentation layer:** Plotly pie chart, metrics, dataframes, CSV export.

This is a multi-step, tool-oriented assistant workflow. The hackathon MVP uses deterministic Python logic for core decisions and an optional LLM for natural-language explanations. It should not be described as a fully autonomous financial agent or a substitute for a regulated advisor.

## 10. Data Model

Each expense record contains:
- `date`
- `merchant`
- `description`
- `category`
- `amount`
- `currency`
- `source` (Manual or Receipt OCR)

Each savings goal contains:
- `name`
- `target`
- `saved`
- `monthly`
- `months`
- `currency`

The MVP stores data in Streamlit session state and supports CSV export. This is not durable storage: data may disappear when a session resets or the app restarts.

## 11. External Services and Cost Controls

- **Tesseract OCR:** open-source OCR installed as a Linux dependency.
- **Country lookup:** optional no-key IP geolocation endpoint; can fail or be inaccurate.
- **Currency conversion:** optional Frankfurter public exchange-rate API; pair coverage and availability may vary.
- **Optional LLM:** Groq-compatible API via a user-supplied key in Streamlit Secrets. Free-tier quotas and model availability may change.
- **Core calculations:** local Python, no API key.

The project does not promise unlimited free use. Any external service may change quotas, availability, or terms.

## 12. Error Handling and Fallbacks

| Component | Failure behavior |
|---|---|
| OCR import/image/OCR | Show warning; allow manual entry |
| IP country lookup | Ask user to select country |
| Currency conversion | Do not convert; clearly report unavailability |
| Optional LLM | Use rules-based coach |
| Category match | Suggest Other; allow manual selection |
| Empty transaction history | Show onboarding prompt instead of chart error |
| Invalid amount | Reject save and explain why |
| Unsupported currency pair | Preserve original amount/currency |

## 13. Risks and Mitigations

- **OCR errors:** require review before saving.
- **Session data loss:** explain limitation and offer CSV export.
- **Incorrect country inference:** provide manual override.
- **Misleading financial guidance:** show educational disclaimer; no security-specific trade calls.
- **Free service outages/quotas:** optional calls with timeouts and fallback.
- **Currency mixing:** only aggregate records in the selected currency.
- **Hackathon deployment risk:** keep dependencies lean and use a single main `app.py`.

## 14. Acceptance Criteria

The MVP is ready for demonstration when:
- The app deploys and opens on Streamlit Community Cloud.
- Budget and currency can be selected.
- Manual expenses can be added and appear in the table and chart.
- Receipt upload/camera UI is available; OCR results can be reviewed and saved where OCR works.
- Categories can be edited.
- Savings goals show a simple contribution-based timeline.
- The money coach shows a budget summary even without an LLM key.
- CSV export works.
- The app displays clear warnings for session-only storage and non-professional financial guidance.
- No secrets are present in repository files.

## 15. Demonstration Script

1. Set a budget in PKR or another supported currency.
2. Add a grocery expense manually.
3. Upload a receipt image and review the extracted amount.
4. Show category pie chart and transaction table.
5. Add a laptop or car savings goal and show estimated months to target.
6. Open Money Coach to view budget-use guidance and investment-risk education.
7. Export transactions as CSV.
8. Demonstrate graceful fallback by leaving the optional LLM key unset.

## 16. Future Roadmap

- Persistent database with authenticated user accounts.
- More robust receipt parsing and multi-language OCR.
- Recurring expense detection and bill reminders.
- Multi-currency transaction normalization with exchange-rate date tracking.
- Localized financial education and verified links to national regulators.
- Optional consent-based economic indicators and market data.
- User-controlled privacy settings and data deletion/export tools.
- More sophisticated agent orchestration with transparent tool logs and approval gates.

## 17. Submission Notes

Submit this PRD with the source repository and the deployed Streamlit URL. State clearly that the MVP uses session-only storage and that OCR/country lookup/optional LLM behavior depends on deployment and external service availability. Do not claim a successful live deployment until the public app URL has been opened and verified.
