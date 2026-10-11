"""
Fallback categorization for the rare transaction where Plaid doesn't return
a personal finance category at all (uncommon, but happens with some
institutions and some sandbox test data). Only called when both a
merchant-match rule AND Plaid's own category come up empty.
"""
import anthropic
from flask import current_app


def ai_guess_category(merchant_name: str, category_names: list[str]) -> str | None:
    api_key = current_app.config.get("ANTHROPIC_API_KEY")
    if not api_key or not merchant_name or not category_names:
        return None

    client = anthropic.Anthropic(api_key=api_key)
    prompt = (
        f'Merchant: "{merchant_name}"\n'
        f"Categories: {', '.join(category_names)}\n\n"
        "Reply with exactly one category name from the list above that best "
        'fits this merchant. If none fit well, reply with "Uncategorized". '
        "Reply with only the category name and nothing else."
    )

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=20,
            messages=[{"role": "user", "content": prompt}],
        )
        guess = response.content[0].text.strip()
        return guess if guess in category_names else None
    except Exception:
        # Never let a flaky AI call break a sync — fall through to
        # Uncategorized, same as if this function returned nothing.
        return None