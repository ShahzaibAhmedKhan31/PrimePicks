from app.database import (
    get_listing,
    get_openai_usage_summary,
    initialize_database,
    list_listings,
    record_openai_usage,
    save_listing,
)
from app.models import ListingContent, ProductData


def test_saved_listing_can_be_reopened_from_sqlite(tmp_path, monkeypatch):
    monkeypatch.setenv("PRIMEPICK_DATA_DIR", str(tmp_path))
    initialize_database()
    product = ProductData(
        source_url="https://www.aliexpress.com/item/123.html",
        title="Portable Reading Lamp",
        description="A USB-powered reading lamp.",
    )
    content = ListingContent(
        title="Portable USB Reading Lamp",
        description="A USB-powered reading lamp.",
        features=["USB power source"],
    )

    saved = save_listing(product, content, "<!doctype html><html></html>")
    reopened = get_listing(saved["id"])

    assert reopened is not None
    assert reopened["content"]["title"] == content.title
    assert reopened["product"]["title"] == product.title
    assert reopened["html"].startswith("<!doctype html>")
    assert list_listings()[0]["id"] == saved["id"]


def test_openai_usage_totals_persist_and_unknown_pricing_is_reported(tmp_path, monkeypatch):
    monkeypatch.setenv("PRIMEPICK_DATA_DIR", str(tmp_path))
    initialize_database()

    record_openai_usage(
        model="gpt-4o-mini",
        input_tokens=1_000,
        output_tokens=500,
        total_tokens=1_500,
        input_price_per_million=0.15,
        output_price_per_million=0.60,
    )
    record_openai_usage(
        model="custom-model",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        input_price_per_million=None,
        output_price_per_million=None,
    )

    summary = get_openai_usage_summary()

    assert summary == {
        "request_count": 2,
        "input_tokens": 1_100,
        "output_tokens": 550,
        "total_tokens": 1_650,
        "estimated_cost_usd": 0.00045,
        "unpriced_request_count": 1,
    }
