"""
Categorization engine for Module 2.

Matches a merchant name (and, as a second pass, the raw message text) against each
category's comma-separated keyword list. One categorizer serves CSV rows, manual
entries, SMS and UPI notifications.

Matching uses word boundaries so a short keyword such as "vi" cannot fire inside
"via UPI" (a real bug with substring matching on genuine bank SMS).
"""
import re
from models.category import Category

DEFAULT_CATEGORIES = {
    "Food": "swiggy,zomato,restaurant,cafe,food,dominos,starbucks,eatery,mcdonald,kfc,pizza,"
            "bakery,chai,tea,hotel,biryani,instamart,blinkit,zepto,bigbasket,juice,canteen",
    "Travel": "uber,ola,irctc,redbus,flight,indigo,railway,metro,fuel,petrol,diesel,rapido,"
              "makemytrip,goibibo,airlines,bus,taxi,fastag,parking,hpcl,bpcl,iocl,petroleum",
    "Shopping": "amazon,flipkart,myntra,ajio,mall,store,shop,meesho,nykaa,dmart,decathlon,"
                "lenskart,croma,reliance,mart,supermarket",
    "Healthcare": "pharmacy,hospital,clinic,apollo,medplus,medical,diagnostic,1mg,pharmeasy,"
                  "netmeds,lab,dental,doctor",
    "Utilities": "electricity,water bill,recharge,broadband,dth,gas,jio,airtel,vi,bsnl,tneb,"
                 "tangedco,bescom,postpaid,prepaid,insurance",
    "Income": "salary,refund,deposit,interest,cashback,dividend",
    "Others": "",
}


def seed_default_categories(db):
    """Create the default categories, and merge in any new default keywords for
    categories that already exist (user-added keywords are never removed)."""
    existing = {c.name: c for c in Category.query.all()}
    changed = False
    for name, keywords in DEFAULT_CATEGORIES.items():
        cat = existing.get(name)
        if cat is None:
            db.session.add(Category(name=name, keywords=keywords))
            changed = True
            continue
        have = [k.strip() for k in (cat.keywords or "").split(",") if k.strip()]
        missing = [k for k in keywords.split(",") if k and k not in have]
        if missing:
            cat.keywords = ",".join(have + missing)
            changed = True
    if changed:
        db.session.commit()


def _keyword_regex(keyword):
    kw = keyword.strip().lower()
    # short words need a closing boundary too ("vi", "gas", "ola"); longer ones may be prefixes
    return re.compile(r"\b" + re.escape(kw) + (r"\b" if len(kw) <= 4 else ""), re.IGNORECASE)


def categorize(merchant, raw_text="", txn_type=None):
    """
    Returns the matching Category (or 'Others').
    txn_type: 'income' -> always the Income category; 'expense' -> never Income.
    """
    categories = Category.query.all()
    by_name = {c.name: c for c in categories}

    if txn_type == "income":
        return by_name.get("Income") or by_name.get("Others")

    candidates = [c for c in categories if c.name != "Income" and c.keywords]
    for text in (merchant or "", raw_text or ""):       # merchant first, then the full message
        if not text.strip():
            continue
        for category in candidates:
            for keyword in category.keywords.split(","):
                if keyword.strip() and _keyword_regex(keyword).search(text):
                    return category
    return by_name.get("Others")
