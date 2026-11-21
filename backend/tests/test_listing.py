import pytest
from pydantic import ValidationError

from app.models import ListingContent, ProductAttribute, ProductData, ProductImage
from app.renderer import render_listing


def _content(title="Rechargeable LED Reading Lamp"):
    return ListingContent(
        title=title,
        description="A flexible reading lamp with adjustable brightness.",
        features=["Flexible neck for angle adjustment", "USB power source"],
        specifications=[ProductAttribute(name="Material", value="ABS")],
        package_contents=["1 lamp", "1 USB cable"],
        usage_instructions=["Charge before first use."],
        warnings=["Keep away from water."],
        review_flags=["Confirm package contents before publishing."],
    )


def _product():
    return ProductData(
        source_url="https://www.aliexpress.com/item/123.html",
        title="Portable Reading Lamp",
        description="Flexible neck with adjustable brightness.",
        images=[ProductImage(url="https://ae01.alicdn.com/kf/lamp.jpg", alt="Lamp")],
    )


def test_product_data_rejects_non_aliexpress_sources_and_local_images():
    with pytest.raises(ValidationError):
        ProductData(source_url="https://example.com/product")
    with pytest.raises(ValidationError):
        ProductImage(url="http://127.0.0.1/private.jpg")


def test_listing_title_must_fit_ebay_limit():
    with pytest.raises(ValidationError):
        _content("A" * 81)


def test_empty_editor_rows_are_ignored_when_validating_content():
    content = _content()
    content.features = ["Flexible neck", ""]
    content.specifications.append(ProductAttribute(name="", value=""))
    content.package_contents.append("")
    normalized = ListingContent.model_validate(content.model_dump())
    assert normalized.features == ["Flexible neck"]
    assert len(normalized.specifications) == 1
    assert normalized.package_contents == ["1 lamp", "1 USB cable"]


def test_render_uses_branded_table_template_and_escapes_content():
    content = _content()
    content.description = "Safe text <script>alert('x')</script>"
    html = render_listing(_product(), content)

    assert "PRIMEPICK GOODS" in html
    assert "Key features" in html
    assert "Package includes" in html
    assert "https://ae01.alicdn.com/kf/lamp.jpg" in html
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<table" in html
    assert "<link" not in html
    assert "<style" not in html
