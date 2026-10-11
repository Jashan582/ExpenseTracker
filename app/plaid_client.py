"""
Thin wrapper around the Plaid SDK. Keeps all Plaid-specific request/response
shapes in one place so routes stay simple.
"""
import plaid
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.accounts_get_request import AccountsGetRequest
from flask import current_app

# Plaid retired the separate "Development" environment — sandbox is free for
# testing, and production is gated behind Plaid approving your use case.
_ENV_HOSTS = {
    "sandbox": plaid.Environment.Sandbox,
    "production": plaid.Environment.Production,
}


def get_plaid_client():
    cfg = current_app.config
    configuration = plaid.Configuration(
        host=_ENV_HOSTS[cfg["PLAID_ENV"]],
        api_key={
            "clientId": cfg["PLAID_CLIENT_ID"],
            "secret": cfg["PLAID_SECRET"],
        },
    )
    api_client = plaid.ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)


def create_link_token(user_id: int) -> str:
    client = get_plaid_client()
    cfg = current_app.config
    request = LinkTokenCreateRequest(
        products=[Products(p) for p in cfg["PLAID_PRODUCTS"]],
        client_name="Expense Tracker",
        country_codes=[CountryCode(c) for c in cfg["PLAID_COUNTRY_CODES"]],
        language="en",
        user=LinkTokenCreateRequestUser(client_user_id=str(user_id)),
    )
    response = client.link_token_create(request)
    return response.link_token


def exchange_public_token(public_token: str):
    client = get_plaid_client()
    request = ItemPublicTokenExchangeRequest(public_token=public_token)
    response = client.item_public_token_exchange(request)
    return response.access_token, response.item_id


def get_accounts(access_token: str):
    client = get_plaid_client()
    request = AccountsGetRequest(access_token=access_token)
    response = client.accounts_get(request)
    return response.accounts


def sync_transactions(access_token: str, cursor: str | None):
    """
    Pulls everything new/changed since `cursor` using Plaid's cursor-based
    sync endpoint (the current recommended approach over /transactions/get).
    Returns (added, modified, removed, next_cursor, has_more).
    """
    client = get_plaid_client()
    added, modified, removed = [], [], []
    has_more = True
    next_cursor = cursor

    while has_more:
        # On the very first sync there's no cursor yet. The newer Plaid SDK
        # requires cursor to be an actual string if it's passed at all, so
        # we omit the kwarg entirely rather than passing None.
        kwargs = {"access_token": access_token}
        if next_cursor:
            kwargs["cursor"] = next_cursor

        request = TransactionsSyncRequest(**kwargs)
        response = client.transactions_sync(request)
        added.extend(response.added)
        modified.extend(response.modified)
        removed.extend(response.removed)
        has_more = response.has_more
        next_cursor = response.next_cursor

    return added, modified, removed, next_cursor