"""
Plaid's Personal Finance Category (PFC) taxonomy has 16 primary categories,
returned as SCREAMING_SNAKE_CASE values (e.g. FOOD_AND_DRINK). This maps
them to names we're comfortable auto-creating as real Category rows.
"""

PFC_PRIMARY_LABELS = {
    "INCOME": "Income",
    "TRANSFER_IN": "Transfers In",
    "TRANSFER_OUT": "Transfers Out",
    "LOAN_PAYMENTS": "Loan Payments",
    "BANK_FEES": "Bank Fees",
    "ENTERTAINMENT": "Entertainment",
    "FOOD_AND_DRINK": "Food and Drink",
    "GENERAL_MERCHANDISE": "Shopping",
    "HOME_IMPROVEMENT": "Home Improvement",
    "MEDICAL": "Health",
    "PERSONAL_CARE": "Personal Care",
    "GENERAL_SERVICES": "Services",
    "GOVERNMENT_AND_NON_PROFIT": "Government & Non-Profit",
    "TRANSPORTATION": "Transportation",
    "TRAVEL": "Travel",
    "RENT_AND_UTILITIES": "Housing & Utilities",
}


def label_for_pfc(primary: str | None) -> str | None:
    """Returns a human-readable category name for a Plaid PFC primary value."""
    if not primary:
        return None
    return PFC_PRIMARY_LABELS.get(primary, primary.replace("_", " ").title())