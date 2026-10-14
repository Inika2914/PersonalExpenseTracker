"""Run with:  python tests/test_parser.py   (no extra packages needed)"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from services.parser import parse_transaction_text as parse, looks_like_payment_text as looks

R = "\u20b9"

# (text, expected amount, type, merchant or None to skip, bank/app or None to skip, kwargs)
POSITIVE = [
    # --- the original demo samples must keep working ---
    ("Rs.450.00 debited from A/c XX1234 to SWIGGY on 11-09-26 via UPI - HDFC Bank", 450, "expense", "Swiggy", "HDFC Bank", {}),
    ("You paid Rs.220 to Uber via Google Pay", 220, "expense", "Uber", "Google Pay", {}),
    ("Rs.25000.00 credited to A/c XX1234 - Salary - SBI", 25000, "income", "Salary", "State Bank of India", {}),
    ("Rs.500.00 credited to A/c XX5678 - Refund - ICICI Bank", 500, "income", "Refund", "ICICI Bank", {}),
    ("Rs.1200.00 received in A/c XX1234 from RAHUL KUMAR via UPI - HDFC Bank", 1200, "income", "Rahul Kumar", "HDFC Bank", {}),
    ("Rs.85.50 credited to A/c XX1234 as Cashback - Axis Bank", 85.5, "income", "Cashback", "Axis Bank", {}),
    ("Rs.320.00 credited to A/c XX9988 - Interest - Kotak Bank", 320, "income", "Interest", "Kotak Bank", {}),
    # --- realistic bank SMS formats ---
    ("Sent Rs.450.00 From HDFC Bank A/C *1234 To SWIGGY On 11/09/26 Ref 123456789012 Not You? Call 18002586161", 450, "expense", "Swiggy", "HDFC Bank", {}),
    ("Dear UPI user A/C X1234 debited by 450.0 on date 11Sep26 trf to SWIGGY Refno 612345678901. If not u? call 1800111109. -SBI", 450, "expense", "Swiggy", "State Bank of India", {}),
    ("ICICI Bank Acct XX123 debited for Rs 450.00 on 11-Sep-26; SWIGGY credited. UPI:612345678901. Call 18002662 for dispute.", 450, "expense", "Swiggy", "ICICI Bank", {}),
    ("INR 450.00 debited A/c no. XX1234 11-09-26 12:30:00 UPI/P2M/123456789012/SWIGGY SMS BLOCK UPI to 18001035577", 450, "expense", "Swiggy", "Axis Bank", {"sender": "AX-AXISBK-S"}),
    ("Sent Rs.450.00 from Kotak Bank AC X1234 to swiggy@upi on 11-09-26.UPI Ref 612345678901.", 450, "expense", "Swiggy", "Kotak Bank", {}),
    ("Rs.1499.00 spent on HDFC Bank Credit Card XX1234 at AMAZON on 11-Sep-26. Avl Lmt Rs.50000.", 1499, "expense", "Amazon", "HDFC Bank", {}),
    ("Rs.1200.00 credited to a/c XX1234 on 11-09-26 by VPA rahul@okhdfc (UPI Ref No 612345678901)", 1200, "income", "Rahul", "HDFC Bank", {}),
    ("Rs 1,23,456.00 credited to A/c XX1234 on 11-09-26. Avl Bal Rs 2,50,000.00", 123456, "income", None, None, {}),
    ("Rs.2000.00 withdrawn from A/c XX1234 at ATM-SBI on 11-09-26. Avl Bal Rs.8000.00", 2000, "expense", "ATM Withdrawal", None, {}),
    ("Avl Bal Rs.5000.00. Rs.450.00 debited from A/c XX1234 to ZOMATO on 11-09-26", 450, "expense", "Zomato", None, {}),
    ("Rs.250.00 spent at CHAI POINT using Debit Card XX1234 on 11-09-26", 250, "expense", "Chai Point", None, {}),
    # --- UPI app notifications ---
    (f"Paid {R}450.00 to Swiggy Store", 450, "expense", "Swiggy Store", None, {"source": "notification", "package": "com.google.android.apps.nbu.paisa.user"}),
    (f"Paid {R}450 Paid to Swiggy", 450, "expense", "Swiggy", None, {"source": "notification", "package": "com.phonepe.app"}),
    (f"Received {R}500 Received from Rahul Kumar", 500, "income", "Rahul Kumar", None, {"source": "notification", "package": "com.phonepe.app"}),
    (f"{R}180 paid to Chai Point successfully", 180, "expense", "Chai Point", None, {"source": "notification", "package": "net.one97.paytm"}),
    (f"Google Pay You received {R}1,500.00 from Anita", 1500, "income", "Anita", "Google Pay", {"source": "notification"}),
]

NEGATIVE = [
    "Your OTP for transaction of Rs.450.00 at SWIGGY is 482913. Do not share with anyone.",
    "Rs.5000.00 will be debited from your A/c on 15-Sep-26 towards loan EMI.",
    "Rahul has requested Rs.500 from you. Pay now to accept.",
    "Your payment of Rs.450.00 to SWIGGY failed. Amount will be refunded if debited.",
    "Your credit card statement is generated. Total amount due Rs.12,345.00, due on 20-Sep-26.",
    "Get up to Rs.500 cashback on your first UPI payment! Click here to apply now.",
    "Hi, are we meeting at 5? I paid for lunch yesterday.",
    "Your A/c XX1234 Avl Bal is Rs.5000.00",
    "",
]

fails = 0
for text, amt, typ, merch, bank, kw in POSITIVE:
    r = parse(text, **kw)
    errs = []
    if not r: errs.append("returned None")
    else:
        if abs(r["amount"] - amt) > 0.001: errs.append(f"amount {r['amount']} != {amt}")
        if r["type"] != typ: errs.append(f"type {r['type']} != {typ}")
        if merch is not None and r["merchant"] != merch: errs.append(f"merchant {r['merchant']!r} != {merch!r}")
        if bank is not None and r["bank_or_app"] != bank: errs.append(f"bank {r['bank_or_app']!r} != {bank!r}")
    if errs:
        fails += 1; print("FAIL:", text[:80], "->", "; ".join(errs))
for text in NEGATIVE:
    if looks(text) or parse(text):
        fails += 1; print("FAIL (should be ignored):", text[:80])

total = len(POSITIVE) + len(NEGATIVE)
print(f"\n{total - fails}/{total} parser checks passed")
sys.exit(1 if fails else 0)
