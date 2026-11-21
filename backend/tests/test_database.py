from app.database import get_listing, initialize_database, list_listings, save_listing
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
