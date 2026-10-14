"""
Parsing engine for Module 2 (Transaction Capture & Processing).

Takes raw text - a bank SMS body or a UPI app notification - and extracts
amount, type (income/expense), merchant/counterparty and bank/app name.

The same function serves every capture path:
  * the web "Simulate" test harness,
  * the real Android SMS receiver and UPI notification listener
    (they POST the raw text to /api/transactions/raw, which calls this).

Real messages are messy, so this module is deliberately defensive:
  * OTPs, pending/failed payments, collect requests and promotions are rejected
  * balance figures ("Avl Bal Rs.5000") are never mistaken for the amount
  * "Credit Card" / "Debit Card" are not mistaken for credit/debit direction
"""
import re
from datetime import datetime

# ---------------------------------------------------------------- bank / app names
BANK_TEXT_PATTERNS = [
    (r"\bHDFC\b", "HDFC Bank"),
    (r"\bICICI\b", "ICICI Bank"),
    (r"\bSBI\b|\bState Bank\b", "State Bank of India"),
    (r"\bAXIS\b", "Axis Bank"),
    (r"\bKOTAK\b", "Kotak Bank"),
    (r"\bPNB\b|\bPunjab National\b", "Punjab National Bank"),
    (r"\bBank of Baroda\b|\bBOB\b", "Bank of Baroda"),
    (r"\bCanara\b", "Canara Bank"),
    (r"\bUnion Bank\b", "Union Bank of India"),
    (r"\bIDFC\b", "IDFC First Bank"),
    (r"\bYes Bank\b", "Yes Bank"),
    (r"\bIndusInd\b", "IndusInd Bank"),
    (r"\bFederal Bank\b", "Federal Bank"),
    (r"\bIDBI\b", "IDBI Bank"),
    (r"\bIndian Bank\b", "Indian Bank"),
    (r"(?<!State )\bBank of India\b", "Bank of India"),
    (r"\bPaytm Payments Bank\b", "Paytm Payments Bank"),
]

# SMS sender IDs look like "VM-HDFCBK" / "AX-SBIUPI-S"; match on the code part.
SENDER_BANK_CODES = [
    ("HDFC", "HDFC Bank"), ("SBI", "State Bank of India"), ("ICICI", "ICICI Bank"),
    ("AXIS", "Axis Bank"), ("KOTAK", "Kotak Bank"), ("PNB", "Punjab National Bank"),
    ("BARODA", "Bank of Baroda"), ("BOB", "Bank of Baroda"), ("CANBNK", "Canara Bank"),
    ("UNIONB", "Union Bank of India"), ("IDFC", "IDFC First Bank"), ("YESBNK", "Yes Bank"),
    ("INDUS", "IndusInd Bank"), ("FEDBNK", "Federal Bank"), ("IDBI", "IDBI Bank"),
    ("INDBNK", "Indian Bank"), ("BOIIND", "Bank of India"), ("PAYTMB", "Paytm Payments Bank"),
]

UPI_APP_TEXT_PATTERNS = [
    (r"google ?pay|gpay", "Google Pay"),
    (r"phonepe", "PhonePe"),
    (r"paytm", "Paytm"),
    (r"\bbhim\b", "BHIM"),
    (r"\bcred\b", "CRED"),
]

# Android package name of the notifying app -> display name
UPI_PACKAGES = {
    "com.google.android.apps.nbu.paisa.user": "Google Pay",
    "com.phonepe.app": "PhonePe",
    "net.one97.paytm": "Paytm",
    "in.org.npci.upiapp": "BHIM",
    "com.dreamplug.androidapp": "CRED",
    "com.mobikwik_new": "MobiKwik",
    "com.freecharge.android": "Freecharge",
}

# ---------------------------------------------------------------- amount
_CUR = r"(?:rs\.?|inr|\u20b9)"
_NUM = r"([\d,]*\d(?:\.\d{1,2})?)"
AMT_VERB = re.compile(
    r"(?:debited|credited|withdrawn|deposited|received|sent|paid|spent|transferred)"
    r"\s*(?:by|with|for|of)?\s*" + _CUR + r"?\s*" + _NUM, re.IGNORECASE)
AMT_CUR = re.compile(_CUR + r"\s*" + _NUM, re.IGNORECASE)
AMT_CUR_AFTER = re.compile(_NUM + r"\s*(?:rs\.?|inr)\b", re.IGNORECASE)
BALANCE_CONTEXT = re.compile(r"bal|avl|available|limit|lmt|outstanding", re.IGNORECASE)

# ---------------------------------------------------------------- direction
DEBIT_RE = re.compile(
    r"\b(?:debited|spent|paid|purchase|withdrawn|sent|transferred)\b"
    r"|\bdebit(?!\s+card)\b|\bpayment of\b|\bupi/(?:dr|p2m|p2p)/", re.IGNORECASE)
CREDIT_RE = re.compile(
    r"\b(?:credited|received|deposited|refunded)\b"
    r"|\bcredit(?!\s+card)\b|\bupi/cr/", re.IGNORECASE)

# ---------------------------------------------------------------- rejections
REJECT_RULES = [
    ("otp", re.compile(r"\b(?:otp|one[- ]time password|verification code|passcode|cvv)\b", re.I)),
    ("pending_or_failed", re.compile(
        r"\b(?:will be debited|has requested|is requesting|requested money|collect request|"
        r"request(?:ed)? for|declined|failed|unsuccessful|not successful|could not be processed|"
        r"pending|expired|reversal initiated|mandate|autopay|auto-pay)\b", re.I)),
    ("due_or_statement", re.compile(
        r"\b(?:payment due|amount due|is due|due on|due by|due date|minimum due|statement|"
        r"bill generated|bill is generated)\b", re.I)),
    ("promotional", re.compile(
        r"\b(?:get up to|apply now|click here|download now|limited period|pre-approved|"
        r"congratulations|exclusive offer|special offer)\b", re.I)),
]

# ---------------------------------------------------------------- merchant extraction
_NAME = r"([A-Za-z0-9@&._' \-]{2,60})"
TO_RE = re.compile(r"\b(?:to|towards|at)\s+(?:vpa\s+|upi id\s+)?" + _NAME, re.IGNORECASE)
FROM_RE = re.compile(r"\bfrom\s+(?:vpa\s+|upi id\s+)?" + _NAME, re.IGNORECASE)
BY_RE = re.compile(r"\bby\s+(?:vpa\s+|upi id\s+)?" + _NAME, re.IGNORECASE)
SLASH_RE = re.compile(r"upi/(?:p2m|p2p|cr|dr)/\d+/" + _NAME, re.IGNORECASE)
CREDITED_AFTER_RE = re.compile(r"[;,]\s*([A-Za-z0-9 &._'\-]{2,40}?)\s+credited\b", re.IGNORECASE)
STOP_SPLIT = re.compile(
    r"\s+(?:on|via|using|through|ref|refno|upi|txn|utr|imps|neft|rtgs|dated|date|avl|bal|"
    r"available|not|if|call|sms|from|for|with|by|successfully|successful|completed|a/c|ac)\b"
    r"|\s+-\s+|\s*[.,;(\[|]", re.IGNORECASE)
REJECT_NAME = re.compile(
    r"^(?:a|your|account|acct|card|wallet|xx+|x\d|\*+|bank|hdfc|icici|sbi|axis|kotak|upi)\b|"
    r"^(?:rs|inr|\u20b9)?\s*[\d,]+", re.IGNORECASE)
LABEL_RE = re.compile(r"\b(salary|refund|cashback|interest|dividend|bonus|reward)\b", re.IGNORECASE)


def _clean_name(raw):
    cand = STOP_SPLIT.split(raw)[0].strip(" -.,'")
    if "@" in cand:                      # UPI id such as swiggy@upi -> "swiggy"
        cand = cand.split("@")[0]
    cand = cand.strip(" -.,'")
    if len(cand) < 2 or cand.isdigit() or REJECT_NAME.match(cand):
        return None
    cand = cand[:40]
    return cand.title() if (cand.isupper() or cand.islower()) else cand


def _first_valid(regex, text):
    for m in regex.finditer(text):
        name = _clean_name(m.group(1))
        if name:
            return name
    return None


# ---------------------------------------------------------------- helpers
def _reject_reason(text):
    for reason, rx in REJECT_RULES:
        if rx.search(text):
            return reason
    return None


def _extract_amount(text):
    m = AMT_VERB.search(text)
    if m:
        value = m.group(1)
    else:
        value = None
        for rx in (AMT_CUR, AMT_CUR_AFTER):
            for mm in rx.finditer(text):
                before = re.split(r"[.;]\s", text[max(0, mm.start() - 18):mm.start()])[-1]
                if BALANCE_CONTEXT.search(before):      # "Avl Bal Rs.5000" is not the amount
                    continue
                value = mm.group(1)
                break
            if value:
                break
    if not value:
        return None
    try:
        amount = float(value.replace(",", ""))
    except ValueError:
        return None
    return amount if 0 < amount < 100_000_000 else None


def _extract_type(text):
    d, c = DEBIT_RE.search(text), CREDIT_RE.search(text)
    if d and c:
        return "expense" if d.start() <= c.start() else "income"
    if d:
        return "expense"
    if c:
        return "income"
    return None


def _extract_merchant(text, ttype):
    low = text.lower()
    if ttype == "expense" and "atm" in low and "withdraw" in low:
        return "ATM Withdrawal"
    name = _first_valid(SLASH_RE, text)
    if name:
        return name
    if ttype == "expense":
        name = _first_valid(TO_RE, text) or _first_valid(CREDITED_AFTER_RE, text)
    else:
        name = _first_valid(FROM_RE, text) or _first_valid(BY_RE, text)
        if not name:
            label = LABEL_RE.search(text)
            name = label.group(1).title() if label else None
    return name


VPA_HANDLES = [
    (r"@ok?hdfc", "HDFC Bank"), (r"@oksbi|@sbi\b", "State Bank of India"),
    (r"@okicici|@icici\b", "ICICI Bank"), (r"@okaxis|@axisbank", "Axis Bank"),
]


def _extract_bank(text, sender):
    for pattern, name in BANK_TEXT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return name
    for pattern, name in VPA_HANDLES:
        if re.search(pattern, text, re.IGNORECASE):
            return name
    if sender:
        code = sender.upper()
        for key, name in SENDER_BANK_CODES:
            if key in code:
                return name
    return None


def _extract_upi_app(text, package):
    if package and package in UPI_PACKAGES:
        return UPI_PACKAGES[package]
    for pattern, name in UPI_APP_TEXT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return name
    return None


def looks_like_payment_text(text):
    """True when the text is a completed money movement (amount + debit/credit wording)
    and is not an OTP, failed/pending payment, bill reminder or promotion."""
    if not text or _reject_reason(text):
        return False
    return _extract_amount(text) is not None and _extract_type(text) is not None


def parse_transaction_text(raw_text, source="sms", sender=None, package=None, received_at=None):
    """
    Main entry point. Returns a dict ready to become a Transaction row, or None when
    the text is not a completed payment message.
    """
    if not looks_like_payment_text(raw_text):
        return None
    ttype = _extract_type(raw_text)
    return {
        "amount": _extract_amount(raw_text),
        "type": ttype,
        "merchant": _extract_merchant(raw_text, ttype) or "Unknown",
        "bank_or_app": (_extract_bank(raw_text, sender)
                        or _extract_upi_app(raw_text, package) or "Unknown"),
        "date": received_at or datetime.utcnow(),
        "source": source,
        "raw_text": raw_text,
    }
