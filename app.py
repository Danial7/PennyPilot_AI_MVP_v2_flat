import io
import math
import re
import uuid
from datetime import date, datetime

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

try:
    import pytesseract
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

APP_NAME = "PennyPilot AI"
CURRENCIES = {
    "PKR — Pakistani Rupee": "PKR", "USD — US Dollar": "USD", "EUR — Euro": "EUR",
    "GBP — British Pound": "GBP", "AED — UAE Dirham": "AED", "SAR — Saudi Riyal": "SAR",
    "INR — Indian Rupee": "INR", "BDT — Bangladeshi Taka": "BDT", "CAD — Canadian Dollar": "CAD",
    "AUD — Australian Dollar": "AUD", "JPY — Japanese Yen": "JPY", "CNY — Chinese Yuan": "CNY",
    "TRY — Turkish Lira": "TRY", "MYR — Malaysian Ringgit": "MYR", "SGD — Singapore Dollar": "SGD",
    "ZAR — South African Rand": "ZAR",
}
COUNTRIES = [
    "Pakistan", "United States", "United Kingdom", "United Arab Emirates", "Saudi Arabia", "India",
    "Canada", "Australia", "Germany", "France", "Turkey", "Malaysia", "Singapore", "South Africa",
    "Bangladesh", "Other"
]
CATEGORIES = [
    "Groceries", "Dining Out", "Housing", "Utilities", "Transport", "Education", "Healthcare",
    "Shopping", "Entertainment", "Personal Care", "Savings", "Debt Payment", "Other"
]
COLUMNS = ["id", "date", "merchant", "description", "category", "amount", "currency", "source"]
DISPLAY_COLUMNS = ["date", "merchant", "description", "category", "amount", "currency", "source"]
ESSENTIAL_CATEGORIES = {"Housing", "Utilities", "Transport", "Education", "Healthcare", "Debt Payment", "Groceries"}
DISCRETIONARY_CATEGORIES = {"Dining Out", "Shopping", "Entertainment", "Personal Care"}

st.set_page_config(page_title=APP_NAME, page_icon="💸", layout="wide")


def safe_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def detect_category(text):
    t = clean_text(text).lower()
    rules = {
        "Groceries": ["grocery", "supermarket", "mart", "rice", "flour", "atta", "soap", "shampoo", "milk", "bread", "vegetable", "fruit", "eggs", "meat", "chicken", "oil", "masala", "detergent"],
        "Dining Out": ["restaurant", "cafe", "coffee", "pizza", "burger", "foodpanda", "takeaway", "dine", "hotel food", "bakery", "kfc", "mcdonald", "domino"],
        "Housing": ["rent", "maintenance", "property", "house"],
        "Utilities": ["electricity", "k-electric", "water bill", "gas bill", "internet", "stormfiber", "mobile bill", "phone bill", "utility"],
        "Transport": ["fuel", "petrol", "diesel", "uber", "careem", "bykea", "bus", "train", "parking", "toll", "rickshaw", "transport"],
        "Education": ["school", "tuition", "academy", "university", "college", "fee", "books", "course"],
        "Healthcare": ["pharmacy", "hospital", "doctor", "clinic", "medicine", "medical", "lab test"],
        "Shopping": ["clothing", "shirt", "shoes", "electronics", "daraz", "laptop", "phone", "purchase"],
        "Entertainment": ["cinema", "movie", "netflix", "game", "concert", "subscription"],
        "Personal Care": ["salon", "barber", "cosmetic", "skincare", "toothpaste", "deodorant"],
        "Debt Payment": ["loan", "credit card payment", "installment", "debt"],
    }
    for category, words in rules.items():
        if any(word in t for word in words):
            return category
    return "Other"


def preprocess_receipt(image):
    """Create several OCR-friendly versions: grayscale, enlarged, contrast and thresholded."""
    img = Image.open(image).convert("RGB")
    # Receipts often contain small text; 2x upscaling helps Tesseract.
    scale = 2.5 if max(img.size) < 2400 else 1.5
    img = img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)
    gray = ImageOps.grayscale(img)
    gray = ImageEnhance.Contrast(gray).enhance(1.8)
    gray = gray.filter(ImageFilter.SHARPEN)
    threshold = gray.point(lambda p: 255 if p > 175 else 0)
    return [gray, threshold]


def extract_receipt(image):
    if not OCR_AVAILABLE:
        return "", "OCR package is unavailable in this deployment."
    try:
        versions = preprocess_receipt(image)
        results = []
        for version in versions:
            for psm in (6, 11):
                text = pytesseract.image_to_string(version, config=f"--psm {psm}")
                if text and text.strip():
                    results.append(text)
        if not results:
            return "", "No readable text found. Try a sharper, well-lit image with the whole receipt visible."
        # Prefer the longest result because it usually preserves more receipt lines.
        best = max(results, key=lambda x: len(x.strip()))
        return best, None
    except Exception as exc:
        return "", f"Could not read this image ({type(exc).__name__}). You can still enter the expense manually."


def normalize_ocr_line(line):
    # Common OCR substitutions in numeric fields.
    line = line.replace("O", "0").replace("o", "0") if re.search(r"(?:total|amount|paid|balance)", line, re.I) else line
    return clean_text(line)


def parse_receipt(text):
    lines = [normalize_ocr_line(x) for x in (text or "").splitlines() if clean_text(x)]
    merchant = ""
    for line in lines[:8]:
        if not re.search(r"receipt|invoice|tax|date|time|cashier|order|total|amount", line, re.I):
            if re.search(r"[A-Za-z]{3,}", line):
                merchant = line[:80]
                break
    if not merchant and lines:
        merchant = lines[0][:80]

    candidates = []
    number_pattern = r"(?<!\w)(?:PKR|Rs\.?|USD|\$|EUR|€|GBP|£|AED|SAR)?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)(?!\w)"
    strong_labels = r"grand\s*total|net\s*total|total\s*amount|amount\s*due|balance\s*due|amount\s*paid|total|paid"
    negative_labels = r"subtotal|tax|vat|discount|change|cash|tender"
    for i, line in enumerate(lines):
        matches = re.findall(number_pattern, line, flags=re.I)
        for n in matches:
            val = safe_float(n)
            if val <= 0:
                continue
            score = 0
            if re.search(strong_labels, line, re.I):
                score += 100
            if re.search(r"grand\s*total|amount\s*due|net\s*total", line, re.I):
                score += 40
            if re.search(negative_labels, line, re.I):
                score -= 35
            # Prefer the lower portion of a receipt where totals usually occur.
            score += i * 0.05
            candidates.append((score, i, val, line))
    amount = max(candidates, default=(0, 0, 0, ""), key=lambda x: (x[0], x[1]))[2]
    return merchant, amount


def detect_country():
    try:
        r = requests.get("https://ipapi.co/json/", timeout=3)
        if r.ok:
            data = r.json()
            return data.get("country_name"), data.get("currency")
    except Exception:
        pass
    return None, None


def try_llm_advice(prompt):
    """Groq OpenAI-compatible chat call with current model defaults and visible diagnostics."""
    try:
        api_key = st.secrets.get("GROQ_API_KEY", "")
        model = st.secrets.get("GROQ_MODEL", "openai/gpt-oss-20b")
        if not api_key:
            return None, "GROQ_API_KEY is not configured in Streamlit Secrets."
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are PennyPilot AI, a cautious personal finance education assistant. Use ONLY the supplied user data. Give concrete observations tied to their actual spending. Do not invent transactions. Do not guarantee returns or recommend specific securities. Do not provide buy/sell instructions. Mention when the dataset is incomplete. Format with a short headline, 3 specific observations, 3 practical next steps, and one caution."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
                "max_tokens": 700,
            },
            timeout=20,
        )
        if not response.ok:
            try:
                detail = response.json().get("error", {}).get("message", response.text[:300])
            except Exception:
                detail = response.text[:300]
            return None, f"Groq request failed ({response.status_code}): {detail}"
        data = response.json()
        return data["choices"][0]["message"]["content"], None
    except Exception as exc:
        return None, f"AI request could not be completed: {type(exc).__name__}: {exc}"


def init_state():
    if "transactions" not in st.session_state:
        st.session_state.transactions = pd.DataFrame(columns=COLUMNS)
    else:
        # Upgrade older sessions that do not have IDs.
        tx = st.session_state.transactions.copy()
        for c in COLUMNS:
            if c not in tx.columns:
                tx[c] = str(uuid.uuid4()) if c == "id" else ""
        if tx["id"].isna().any() or (tx["id"].astype(str).str.len() < 5).any():
            tx["id"] = [str(uuid.uuid4()) for _ in range(len(tx))]
        st.session_state.transactions = tx[COLUMNS]
    if "goals" not in st.session_state:
        st.session_state.goals = []
    if "budget" not in st.session_state:
        st.session_state.budget = 100000.0
    if "currency" not in st.session_state:
        st.session_state.currency = "PKR"
    if "country" not in st.session_state:
        country, _ = detect_country()
        st.session_state.country = country if country in COUNTRIES else "Pakistan"


def add_transaction(tx):
    row = {c: tx.get(c, "") for c in COLUMNS}
    row["id"] = row["id"] or str(uuid.uuid4())
    row["amount"] = safe_float(row["amount"])
    if row["amount"] <= 0:
        raise ValueError("Amount must be greater than zero.")
    row["date"] = pd.to_datetime(row["date"], errors="coerce").date().isoformat() if pd.notna(pd.to_datetime(row["date"], errors="coerce")) else date.today().isoformat()
    row["merchant"] = clean_text(row["merchant"]) or "Not specified"
    row["description"] = clean_text(row["description"])
    row["category"] = row["category"] if row["category"] in CATEGORIES else detect_category(f"{row['merchant']} {row['description']}")
    row["currency"] = row["currency"] if row["currency"] in CURRENCIES.values() else st.session_state.currency
    row["source"] = clean_text(row["source"]) or "Manual"
    st.session_state.transactions = pd.concat([st.session_state.transactions, pd.DataFrame([row])], ignore_index=True)[COLUMNS]


def money(value, currency):
    return f"{currency} {value:,.2f}"


def visible_df():
    df = st.session_state.transactions.copy()
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    return df[df["currency"] == st.session_state.currency].copy()


def build_financial_agent(budget, df, currency, goals):
    """Calculate financial facts deterministically; the optional LLM only explains them."""
    spent = float(df["amount"].sum()) if not df.empty else 0.0
    remaining = budget - spent
    ratio = spent / budget if budget > 0 else 0.0
    today = date.today()
    month_days = pd.Timestamp(today).days_in_month
    day_number = today.day
    projected = spent / day_number * month_days if day_number and spent else 0.0

    context = {
        "spent": spent, "remaining": remaining, "ratio": ratio,
        "projected": projected, "transactions": len(df),
        "top_category": "", "top_category_amount": 0.0,
        "top_category_pct": 0.0, "discretionary": 0.0,
        "essential": 0.0, "category_totals": {},
        "largest_transaction": None, "goal_analysis": [],
        "recommended_actions": [], "budget_status": "No data"
    }
    if df.empty:
        return [], context

    cats = df.groupby("category")["amount"].sum().sort_values(ascending=False)
    discretionary = float(df[df["category"].isin(DISCRETIONARY_CATEGORIES)]["amount"].sum())
    essential = float(df[df["category"].isin(ESSENTIAL_CATEGORIES)]["amount"].sum())
    top_cat, top_val = str(cats.index[0]), float(cats.iloc[0])
    largest = df.nlargest(1, "amount").iloc[0]

    if ratio >= 1:
        status = "Over budget"
    elif projected > budget and day_number < month_days:
        status = "At risk"
    elif ratio >= 0.85:
        status = "Watch"
    else:
        status = "On track"

    context.update({
        "top_category": top_cat, "top_category_amount": top_val,
        "top_category_pct": top_val / spent if spent else 0,
        "discretionary": discretionary, "essential": essential,
        "category_totals": {str(k): float(v) for k, v in cats.items()},
        "budget_status": status,
        "largest_transaction": {
            "merchant": str(largest["merchant"]),
            "amount": float(largest["amount"]),
            "category": str(largest["category"]),
            "date": str(largest["date"])
        }
    })

    # Connect discretionary spending to savings goals.
    for goal in goals:
        if goal.get("currency") != currency:
            continue
        target = float(goal.get("target", 0))
        saved = float(goal.get("saved", 0))
        monthly = float(goal.get("monthly", 0))
        gap = max(target - saved, 0)
        current_months = math.ceil(gap / monthly) if gap and monthly > 0 else 0
        opportunities = []
        for category in DISCRETIONARY_CATEGORIES:
            value = float(cats.get(category, 0))
            if value > 0:
                saving = value * 0.20
                new_monthly = monthly + saving
                new_months = math.ceil(gap / new_monthly) if gap and new_monthly > 0 else 0
                opportunities.append({
                    "category": category,
                    "potential_saving": saving,
                    "new_monthly": new_monthly,
                    "new_months": new_months,
                    "months_saved": max(current_months - new_months, 0)
                })
        opportunities.sort(key=lambda x: x["potential_saving"], reverse=True)
        context["goal_analysis"].append({
            "name": str(goal.get("name", "Goal")),
            "gap": gap, "monthly": monthly,
            "current_months": current_months,
            "opportunities": opportunities[:3]
        })

    actions = []
    if ratio >= 1:
        actions.append(f"Reduce discretionary spending until the recorded {money(abs(remaining), currency)} budget gap is recovered.")
    elif projected > budget and day_number < month_days:
        actions.append(f"Your current pace points to about {money(projected, currency)} by month-end; protect the remaining {money(max(remaining, 0), currency)}.")
    elif ratio >= 0.85:
        actions.append(f"Keep the remaining {money(max(remaining, 0), currency)} for essential or already-planned expenses.")
    else:
        actions.append(f"Keep at least {money(max(remaining, 0), currency)} uncommitted until the end of the budget period.")

    discretionary_ranked = sorted(
        [(c, float(cats.get(c, 0))) for c in DISCRETIONARY_CATEGORIES if float(cats.get(c, 0)) > 0],
        key=lambda x: x[1], reverse=True
    )
    if discretionary_ranked:
        c, value = discretionary_ranked[0]
        actions.append(f"Review {c}: a 20% reduction would free about {money(value * 0.20, currency)} based on recorded spending.")
    else:
        actions.append("Most recorded spending is essential, so the coach is avoiding arbitrary cuts to essential categories.")

    best = None
    for goal in context["goal_analysis"]:
        for opp in goal["opportunities"]:
            if best is None or opp["months_saved"] > best[1]["months_saved"]:
                best = (goal, opp)
    if best and best[1]["potential_saving"] > 0:
        goal, opp = best
        actions.append(f"For {goal['name']}, redirecting about {money(opp['potential_saving'], currency)}/month from {opp['category']} could shorten the simple goal estimate from {goal['current_months']} to {opp['new_months']} month(s).")
    context["recommended_actions"] = actions[:3]

    lines = [
        f"You have recorded {money(spent, currency)} against a {money(budget, currency)} monthly budget ({ratio:.0%} recorded).",
        f"{top_cat} is your largest recorded category at {money(top_val, currency)} ({top_val / spent:.0%} of recorded spending).",
        f"At the current pace, recorded spending would be roughly {money(projected, currency)} by month-end; this is a pace estimate, not a guaranteed forecast.",
        f"Your largest recorded transaction is {money(float(largest['amount']), currency)} at {largest['merchant']} ({largest['category']})."
    ]
    if discretionary:
        lines.append(f"Recorded discretionary spending is {money(discretionary, currency)} ({discretionary / spent:.0%} of spending).")
    return lines, context

# Compatibility for any older reference.
build_personal_coach = build_financial_agent


def investment_education(country, currency, remaining):
    return (
        f"Country selected: {country}. Currency: {currency}. These are educational considerations, not personalized investment instructions.\n\n"
        "1. Emergency reserve: consider building accessible savings for unexpected expenses before taking market risk.\n"
        "2. Stocks/funds: prices can fall; learn about diversification, fees, regulation, and time horizon. Avoid investing money needed soon.\n"
        "3. Gold: prices fluctuate and spreads/storage can affect returns; it does not generate interest or dividends.\n"
        "4. Crypto: highly volatile and may involve fraud, custody, platform, and regulatory risks.\n"
        "5. Local rules: check the relevant country's regulator and tax treatment before acting.\n\n"
        f"Recorded budget remaining this month: {money(max(remaining, 0), currency)}. This may be incomplete if expenses have not been recorded."
    )


def normalize_import_columns(raw):
    aliases = {
        "date": ["date", "transaction date", "expense date", "day"],
        "merchant": ["merchant", "payee", "vendor", "store", "description merchant"],
        "description": ["description", "details", "item", "note", "notes"],
        "category": ["category", "type", "expense category"],
        "amount": ["amount", "expense", "value", "total", "price", "cost"],
        "currency": ["currency", "curr", "ccy"],
        "source": ["source", "entry source"],
    }
    rename = {}
    normalized = {re.sub(r"[^a-z0-9]+", " ", str(c).lower()).strip(): c for c in raw.columns}
    for target, names in aliases.items():
        for name in names:
            key = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
            if key in normalized:
                rename[normalized[key]] = target
                break
    df = raw.rename(columns=rename).copy()
    for c in COLUMNS[1:]:
        if c not in df.columns:
            df[c] = ""
    if "currency" not in rename.values():
        df["currency"] = st.session_state.currency
    if "source" not in rename.values():
        df["source"] = "Spreadsheet import"
    if "category" not in rename.values():
        df["category"] = [detect_category(f"{m} {d}") for m, d in zip(df["merchant"], df["description"])]
    return df[[c for c in COLUMNS if c != "id"]]


def prepare_import(raw):
    df = normalize_import_columns(raw)
    df["amount"] = pd.to_numeric(df["amount"].astype(str).str.replace(",", "", regex=False).str.extract(r"(-?\d+(?:\.\d+)?)")[0], errors="coerce")
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df["merchant"] = df["merchant"].fillna("").map(clean_text)
    df["description"] = df["description"].fillna("").map(clean_text)
    df["currency"] = df["currency"].fillna(st.session_state.currency).astype(str).str.upper().str.strip()
    df["category"] = df.apply(lambda r: r["category"] if r["category"] in CATEGORIES else detect_category(f"{r['merchant']} {r['description']}"), axis=1)
    df["source"] = df["source"].fillna("Spreadsheet import").astype(str)
    return df


init_state()
st.title("💸 PennyPilot AI")
st.caption("A privacy-conscious personal budget, receipt and savings-goal assistant")
st.info("Hackathon MVP: records are stored in this active app session and may be lost when the session resets. Do not enter bank passwords, card numbers, or other sensitive credentials. This is an educational tool, not regulated financial advice.")

with st.sidebar:
    st.header("Your financial profile")
    selected_label = st.selectbox("Monthly budget currency", list(CURRENCIES.keys()), index=list(CURRENCIES.values()).index(st.session_state.currency) if st.session_state.currency in CURRENCIES.values() else 0)
    st.session_state.currency = CURRENCIES[selected_label]
    st.session_state.budget = st.number_input("Approx. monthly budget", min_value=0.0, value=float(st.session_state.budget), step=1000.0, format="%.2f")
    detected = st.session_state.get("country")
    st.caption(f"Best-effort country detection: {detected or 'not detected'}")
    country_index = COUNTRIES.index(detected) if detected in COUNTRIES else 0
    st.session_state.country = st.selectbox("Country (edit if incorrect)", COUNTRIES, index=country_index)
    st.caption("Country detection uses a no-key IP lookup when available. It can be inaccurate; your selection takes priority.")

df = visible_df()
total_spent = float(df["amount"].sum()) if not df.empty else 0.0
remaining = st.session_state.budget - total_spent

tabs = st.tabs(["📊 Dashboard", "🧾 Add expense", "📥 Import expenses", "🎯 Savings goals", "🧠 Money coach", "📤 Export"])

with tabs[0]:
    st.subheader("Monthly overview")
    c1, c2, c3 = st.columns(3)
    c1.metric("Monthly budget", money(st.session_state.budget, st.session_state.currency))
    c2.metric("Recorded spending", money(total_spent, st.session_state.currency))
    c3.metric("Budget remaining", money(remaining, st.session_state.currency), delta="Over budget" if remaining < 0 else "Available")
    if st.session_state.budget > 0:
        st.progress(min(max(total_spent / st.session_state.budget, 0.0), 1.0), text=f"{total_spent / st.session_state.budget:.0%} of budget recorded")
    if df.empty:
        st.write("No expenses recorded in this currency yet. Add one manually, upload a receipt, or import a CSV/Excel file.")
    else:
        left, right = st.columns([1, 1])
        category_totals = df.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
        with left:
            st.markdown("**Spending by category**")
            fig = px.pie(category_totals, values="amount", names="category", hole=0.35)
            st.plotly_chart(fig, use_container_width=True)
        with right:
            st.markdown("**Recent transactions**")
            st.dataframe(df.sort_values("date", ascending=False)[DISPLAY_COLUMNS], use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Remove an expense")
    all_tx = st.session_state.transactions.copy()
    if all_tx.empty:
        st.caption("There are no expenses to remove.")
    else:
        choices = {}
        for _, row in all_tx.iterrows():
            label = f"{row['date']} · {row['merchant']} · {row['currency']} {safe_float(row['amount']):,.2f} · {row['category']}"
            choices[label] = row["id"]
        selected = st.multiselect("Select one or more expenses to remove", list(choices.keys()), key="delete_expenses")
        if selected and st.button("Delete selected expense(s)", type="secondary"):
            ids = {choices[x] for x in selected}
            st.session_state.transactions = st.session_state.transactions[~st.session_state.transactions["id"].isin(ids)].reset_index(drop=True)
            st.session_state.pop("delete_expenses", None)
            st.success(f"Deleted {len(ids)} expense(s).")
            st.rerun()
    st.caption("Deleting an expense removes it from the current session and from future CSV exports.")

with tabs[1]:
    st.subheader("Record an expense")
    method = st.radio("Choose entry method", ["Manual entry", "Upload receipt image", "Take receipt photo"], horizontal=True)
    if method == "Manual entry":
        with st.form("manual_expense_form", clear_on_submit=True):
            d = st.date_input("Date", value=date.today())
            merchant = st.text_input("Merchant / payee", placeholder="e.g., local supermarket")
            description = st.text_input("What did you buy?", placeholder="e.g., shampoo, rice and flour")
            amount = st.number_input(f"Amount ({st.session_state.currency})", min_value=0.0, step=100.0)
            suggested = detect_category(f"{merchant} {description}")
            category = st.selectbox("Category", CATEGORIES, index=CATEGORIES.index(suggested))
            submitted = st.form_submit_button("Save expense", type="primary")
            if submitted:
                try:
                    add_transaction({"date": d.isoformat(), "merchant": merchant, "description": description, "category": category, "amount": amount, "currency": st.session_state.currency, "source": "Manual"})
                    st.success("Expense saved for this session.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
    else:
        uploaded = st.camera_input("Take a receipt photo") if method == "Take receipt photo" else st.file_uploader("Upload a receipt or screenshot", type=["png", "jpg", "jpeg", "webp"])
        if uploaded:
            st.image(uploaded, caption="Receipt image", use_container_width=True)
            if st.button("Extract receipt details", type="primary"):
                text, error = extract_receipt(uploaded)
                st.session_state["ocr_text"] = text
                st.session_state["ocr_error"] = error
                merchant, amount = parse_receipt(text)
                st.session_state["ocr_merchant"] = merchant
                st.session_state["ocr_amount"] = amount
            if st.session_state.get("ocr_error"):
                st.warning(st.session_state["ocr_error"])
            if st.session_state.get("ocr_text"):
                st.markdown("**Extracted text — please verify before saving**")
                st.text_area("OCR result", value=st.session_state["ocr_text"], height=180, key="ocr_review")
                with st.form("receipt_save_form"):
                    merchant = st.text_input("Merchant / payee", value=st.session_state.get("ocr_merchant", ""))
                    description = st.text_input("Purchase description", value="Receipt purchase")
                    amount = st.number_input(f"Total amount ({st.session_state.currency})", min_value=0.0, value=max(0.0, safe_float(st.session_state.get("ocr_amount"))), step=100.0)
                    category = st.selectbox("Category", CATEGORIES, index=CATEGORIES.index(detect_category(f"{merchant} {description}")))
                    d = st.date_input("Expense date", value=date.today(), key="receipt_date")
                    save_receipt = st.form_submit_button("Save verified expense", type="primary")
                    if save_receipt:
                        try:
                            add_transaction({"date": d.isoformat(), "merchant": merchant, "description": description, "category": category, "amount": amount, "currency": st.session_state.currency, "source": "Receipt OCR"})
                            for key in ["ocr_text", "ocr_error", "ocr_merchant", "ocr_amount"]:
                                st.session_state.pop(key, None)
                            st.success("Verified expense saved.")
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
                st.caption("OCR now uses enlarged/contrast-enhanced and thresholded passes, but you should still verify the extracted total before saving.")

with tabs[2]:
    st.subheader("Add multiple expenses at once")
    st.write("Upload a CSV or Excel spreadsheet. PennyPilot will map common column names, suggest categories, validate amounts/dates, show a preview, and only add rows after you confirm.")
    st.info("Recommended columns: Date, Merchant, Description, Category, Amount, Currency. Category and Currency can be omitted; PennyPilot will suggest them/use your selected currency.")
    file = st.file_uploader("Upload CSV or Excel file", type=["csv", "xlsx", "xls"], key="bulk_expense_file")
    if file:
        try:
            raw = pd.read_csv(file) if file.name.lower().endswith(".csv") else pd.read_excel(file)
            imported = prepare_import(raw)
            invalid = imported[imported["amount"].isna() | (imported["amount"] <= 0) | imported["date"].isna()].copy()
            unsupported = imported[~imported["currency"].isin(CURRENCIES.values())].copy()
            st.write(f"Rows detected: **{len(imported)}**")
            if not invalid.empty:
                st.warning(f"{len(invalid)} row(s) have an invalid/missing date or amount and will not be imported.")
            if not unsupported.empty:
                st.warning(f"{len(unsupported)} row(s) use an unsupported currency and will not be imported.")
            valid = imported.drop(index=invalid.index).copy()
            valid = valid[valid["currency"].isin(CURRENCIES.values())].copy()
            valid["date"] = valid["date"].astype(str)
            valid = valid[["date", "merchant", "description", "category", "amount", "currency", "source"]]
            if valid.empty:
                st.error("No valid rows are available to import. Check the spreadsheet columns and values.")
            else:
                st.markdown("**Preview — review before importing**")
                edited = st.data_editor(valid, use_container_width=True, hide_index=True, num_rows="dynamic", key="bulk_preview", column_config={"amount": st.column_config.NumberColumn("amount", min_value=0.01, format="%.2f")})
                if st.button("Import these expenses", type="primary"):
                    added = 0
                    for _, row in edited.iterrows():
                        try:
                            add_transaction(row.to_dict())
                            added += 1
                        except ValueError:
                            pass
                    st.success(f"Imported {added} expense(s).")
                    st.rerun()
        except Exception as exc:
            st.error(f"Could not read this spreadsheet: {type(exc).__name__}: {exc}")

with tabs[3]:
    st.subheader("Plan a savings goal")
    st.write("Add a target and PennyPilot estimates a timeline from the monthly contribution you choose.")
    with st.form("goal_form", clear_on_submit=True):
        goal_name = st.text_input("Goal", placeholder="e.g., laptop, car, education fund")
        target = st.number_input(f"Target amount ({st.session_state.currency})", min_value=1.0, value=100000.0, step=5000.0)
        saved = st.number_input(f"Already saved ({st.session_state.currency})", min_value=0.0, value=0.0, step=1000.0)
        contribution = st.number_input(f"Planned monthly contribution ({st.session_state.currency})", min_value=0.0, value=5000.0, step=1000.0)
        goal_submit = st.form_submit_button("Add savings goal", type="primary")
        if goal_submit:
            if not goal_name.strip():
                st.error("Enter a name for your goal.")
            elif contribution <= 0 and saved < target:
                st.error("Monthly contribution must be greater than zero.")
            else:
                months = math.ceil(max(target - saved, 0) / contribution) if contribution > 0 else 0
                st.session_state.goals.append({"name": goal_name.strip(), "target": target, "saved": saved, "monthly": contribution, "months": months, "currency": st.session_state.currency})
                st.success("Goal added.")
                st.rerun()
    if st.session_state.goals:
        for idx, goal in enumerate(st.session_state.goals):
            if goal["currency"] != st.session_state.currency:
                st.caption(f"{goal['name']}: saved in {goal['currency']}; change budget currency to view matching goals.")
                continue
            months = goal["months"]
            est_date = (pd.Timestamp.today().normalize() + pd.DateOffset(months=months)).date() if months else date.today()
            st.markdown(f"**{goal['name']}** — {money(goal['target'], goal['currency'])}")
            st.progress(min(goal["saved"] / goal["target"], 1.0))
            st.write(f"Monthly contribution: {money(goal['monthly'], goal['currency'])} · Estimated time: {months} month(s) · Approx. target date: {est_date}")
            if st.button("Delete goal", key=f"del_goal_{idx}"):
                st.session_state.goals.pop(idx)
                st.rerun()
            st.divider()
    else:
        st.info("No goals added yet.")

with tabs[4]:
    st.subheader("🧠 Your Financial Agent")
    st.caption("PennyPilot calculates the financial facts first. Optional AI explains those facts in plain language.")

    coach_lines, coach_context = build_financial_agent(
        st.session_state.budget, df, st.session_state.currency, st.session_state.goals
    )

    if df.empty:
        st.info("Add several expenses first. The Financial Agent needs recorded spending to produce meaningful personal analysis.")
    else:
        st.markdown("### 🔎 1. Financial Snapshot")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Recorded spending", money(coach_context["spent"], st.session_state.currency))
        k2.metric("Budget used", f"{coach_context['ratio']:.0%}")
        k3.metric("Budget health", coach_context["budget_status"])
        k4.metric("Month-end pace", money(coach_context["projected"], st.session_state.currency))

        status = coach_context["budget_status"]
        if status == "Over budget":
            st.error("Recorded spending has already exceeded the stated monthly budget.")
        elif status == "At risk":
            st.warning("Your current spending pace indicates a possible month-end budget overrun.")
        elif status == "Watch":
            st.warning("A large portion of the budget has already been recorded.")
        else:
            st.success("Recorded spending is currently below the budget threshold.")

        st.markdown("### 📊 2. What's Driving Your Spending?")
        cat = pd.Series(coach_context["category_totals"]).sort_values(ascending=False)
        left, right = st.columns(2)
        with left:
            st.dataframe(
                pd.DataFrame({
                    "Category": cat.index,
                    "Recorded amount": [money(x, st.session_state.currency) for x in cat.values],
                    "% of spending": [f"{x / cat.sum():.0%}" for x in cat.values]
                }),
                use_container_width=True, hide_index=True
            )
        with right:
            fig = px.bar(
                pd.DataFrame({"Category": cat.index, "Amount": cat.values}),
                x="Amount", y="Category", orientation="h",
                title="Recorded spending by category"
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("### 🎯 3. What Should You Change?")
        for i, action in enumerate(coach_context["recommended_actions"], 1):
            st.write(f"**{i}.** {action}")

        lt = coach_context.get("largest_transaction")
        if lt:
            st.info(
                f"Largest recorded transaction: **{lt['merchant']} — {money(lt['amount'], st.session_state.currency)}** "
                f"({lt['category']}). Review whether it was planned, one-off, or recurring."
            )

        st.markdown("### 🎯 4. Goal Impact")
        if coach_context["goal_analysis"]:
            for goal in coach_context["goal_analysis"]:
                st.markdown(f"**{goal['name']}**")
                st.write(
                    f"Remaining: **{money(goal['gap'], st.session_state.currency)}** · "
                    f"Current contribution: **{money(goal['monthly'], st.session_state.currency)}/month** · "
                    f"Estimated time: **{goal['current_months']} month(s)**."
                )
                if goal["opportunities"]:
                    best = goal["opportunities"][0]
                    st.success(
                        f"A 20% reduction in {best['category']} would free about "
                        f"{money(best['potential_saving'], st.session_state.currency)}/month "
                        f"and could shorten the simple estimate by about {best['months_saved']} month(s)."
                    )
        else:
            st.caption("Add a savings goal to see how spending changes could affect your target timeline.")

        st.markdown("### 📅 5. Your Next 7 Days")
        top_disc = sorted(
            [(c, float(coach_context["category_totals"].get(c, 0))) for c in DISCRETIONARY_CATEGORIES
             if float(coach_context["category_totals"].get(c, 0)) > 0],
            key=lambda x: x[1], reverse=True
        )
        weekly = []
        if top_disc:
            c, value = top_disc[0]
            weekly.append(f"Set a personal ceiling for {c}; recorded monthly spending is already {money(value, st.session_state.currency)}.")
        weekly.append(f"Before adding a non-essential expense, check that {money(max(coach_context['remaining'], 0), st.session_state.currency)} remains available.")
        if coach_context["goal_analysis"]:
            weekly.append(f"Keep your {coach_context['goal_analysis'][0]['name']} contribution separate from everyday spending if possible.")
        for item in weekly[:3]:
            st.write("• " + item)

    st.divider()
    st.markdown("### 🤖 Optional AI Explanation")
    st.caption("AI receives calculated financial facts; it is not asked to invent transactions or provide security-specific buy/sell instructions.")

    if st.button("Generate personalized AI explanation", type="primary", disabled=df.empty):
        prompt = f"""
You are the explanation layer of PennyPilot AI.

Use ONLY these calculated facts. Do not invent transactions or financial history.
Do not recommend a particular stock, crypto token, fund, security, or gold product.
Do not give buy/sell instructions. Keep the advice practical and non-judgmental.

Country: {st.session_state.country}
Currency: {st.session_state.currency}
Monthly budget: {st.session_state.budget:.2f}
Recorded spending: {coach_context['spent']:.2f}
Remaining budget: {coach_context['remaining']:.2f}
Budget used: {coach_context['ratio']:.0%}
Budget health: {coach_context['budget_status']}
Month-end pace estimate: {coach_context['projected']:.2f}
Transaction count: {len(df)}
Largest category: {coach_context['top_category']}
Largest category amount: {coach_context['top_category_amount']:.2f}
Largest category share: {coach_context['top_category_pct']:.0%}
Discretionary spending: {coach_context['discretionary']:.2f}
Essential spending: {coach_context['essential']:.2f}
Category totals: {coach_context['category_totals']}
Largest transaction: {coach_context['largest_transaction']}
Goal analysis: {coach_context['goal_analysis']}
Recommended actions: {coach_context['recommended_actions']}

Respond using exactly these sections:
## My financial picture
2-3 sentences based on the numbers.

## What is driving it
3 bullets tied to actual categories or numbers.

## What I would focus on next
3 concrete actions.

## Impact on my goal
Explain the most relevant goal effect, or say no goal was provided.

## One thing to watch
One specific caution based on the data.

End by saying the analysis uses only recorded expenses and is educational, not regulated financial advice.
"""
        with st.spinner("Analyzing your actual spending and goals..."):
            answer, error = try_llm_advice(prompt)
        if answer:
            st.markdown(answer)
        else:
            st.error(error or "The AI explanation could not be generated.")
            st.info("The deterministic Financial Agent above remains available without the AI service.")


with tabs[5]:
    st.subheader("Export and session data")
    all_df = st.session_state.transactions.copy()
    if all_df.empty:
        st.info("No transactions to export yet.")
    else:
        st.dataframe(all_df[DISPLAY_COLUMNS], use_container_width=True, hide_index=True)
        st.download_button("Export all transactions as CSV", all_df[DISPLAY_COLUMNS].to_csv(index=False).encode("utf-8"), file_name="pennypilot_all_transactions.csv", mime="text/csv")
    st.warning("This MVP does not have accounts or a permanent database. Session data is not suitable for long-term financial recordkeeping.")
    if st.button("Clear all session transactions and goals", type="secondary"):
        st.session_state.transactions = pd.DataFrame(columns=COLUMNS)
        st.session_state.goals = []
        for key in ["ocr_text", "ocr_error", "ocr_merchant", "ocr_amount", "bulk_expense_file", "bulk_preview"]:
            st.session_state.pop(key, None)
        st.success("Session records cleared.")
        st.rerun()

st.divider()
st.caption("PennyPilot AI · Hackathon prototype · Estimates are not guarantees. Verify all receipt data and consult a qualified professional for regulated financial decisions.")
