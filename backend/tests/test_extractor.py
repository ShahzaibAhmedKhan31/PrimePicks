from app.extractor import ExtractionError, looks_like_verification, parse_product_html, validate_aliexpress_url


def test_parse_product_html_extracts_available_details():
    html = """
    <html><head><meta property="og:title" content="Portable Reading Lamp">
    <meta property="og:image" content="https://ae01.alicdn.com/kf/lamp.jpg"></head>
    <body><h1>Portable Reading Lamp</h1>
    <div id="product-description">
      <p>Flexible neck with adjustable brightness for reading.</p>
      <p>Package includes: 1 x lamp, 1 x USB cable</p>
      <p>Warning: Keep away from water.</p>
      <p>Instructions: Charge before first use.</p>
    </div>
    <table class="specification"><tr><td>Material</td><td>ABS</td></tr>
      <tr><td>Power source</td><td>USB</td></tr></table>
    <select name="color"><option>White</option><option>Black</option></select>
    <img src="https://ae01.alicdn.com/kf/lamp-side.jpg" alt="Lamp side view" width="500" height="500">
    </body></html>
    """
    product = parse_product_html(html, "https://www.aliexpress.com/item/123.html")

    assert product.title == "Portable Reading Lamp"
    assert "adjustable brightness" in product.description
    assert {item.name for item in product.specifications} == {"Material", "Power source"}
    assert any("White" in option and "Black" in option for option in product.variations)
    assert len(product.images) == 2
    assert any("USB cable" in item for item in product.package_contents)
    assert all("Keep away from water" not in item for item in product.package_contents)
    assert any("Keep away from water" in item for item in product.warnings)
    assert any("Charge before first use" in item for item in product.usage_instructions)


def test_missing_product_information_is_flagged():
    product = parse_product_html("<html><body><main>Just a store page</main></body></html>", "https://www.aliexpress.com/item/123.html")
    assert not product.title
    assert not product.description
    assert len(product.missing_info) >= 3


def test_json_ld_is_used_as_a_fallback_for_product_details():
    html = '''
    <html><head><script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Product","name":"USB Desk Light",
     "description":"A compact USB desk light with a flexible neck and two brightness settings.",
     "image":["https://ae01.alicdn.com/kf/desk-light.jpg"],
     "additionalProperty":[{"@type":"PropertyValue","name":"Power source","value":"USB"}]}
    </script></head><body></body></html>
    '''
    product = parse_product_html(html, "https://www.aliexpress.com/item/456.html")
    assert product.title == "USB Desk Light"
    assert "flexible neck" in product.description
    assert product.specifications[0].value == "USB"
    assert product.images[0].url.endswith("desk-light.jpg")


def test_open_graph_title_is_preferred_over_the_visible_heading():
    html = """
    <html><head><meta property="og:title" content="Metadata Product Title"></head>
    <body><h1>Generic visible heading</h1></body></html>
    """
    product = parse_product_html(html, "https://www.aliexpress.com/item/789.html")

    assert product.title == "Metadata Product Title"


def test_complete_ai_overview_is_used_before_metadata_description():
    html = """
    <html><head>
      <meta property="og:title" content="Adjustable Desk Lamp">
      <meta name="description" content="Short search metadata summary.">
    </head><body>
      <section class="item-overview">
        <h2>AI Overview of Item</h2>
        <div><p>The lamp has an adjustable neck and three brightness levels.</p>
        <p>It is USB powered and includes a cable in the package.</p></div>
      </section>
      <section><h2>Other item details</h2><p>This unrelated text must not replace the overview.</p></section>
    </body></html>
    """
    product = parse_product_html(html, "https://www.aliexpress.com/item/789.html")

    assert product.description == (
        "The lamp has an adjustable neck and three brightness levels.\n"
        "It is USB powered and includes a cable in the package."
    )
    assert "Short search metadata summary" not in product.description
    assert "unrelated text" not in product.description


def test_metadata_description_is_preferred_when_no_ai_overview_exists():
    html = """
    <html><head><meta name="description" content="Metadata product description for the listing."></head>
    <body><div id="product-description">A longer visible description that is not the metadata fallback.</div></body></html>
    """
    product = parse_product_html(html, "https://www.aliexpress.com/item/789.html")

    assert product.description == "Metadata product description for the listing."


def test_embedded_scraped_json_metadata_and_ai_overview_are_used():
    html = '''
    <html><head><script type="application/json">
    {"metadata":{"og:title":"JSON Product Title","description":"Metadata fallback text.",
      "aiOverviewOfItem":"Complete AI overview details from the item data."}}
    </script></head><body><h1>Different visible title</h1></body></html>
    '''
    product = parse_product_html(html, "https://www.aliexpress.com/item/789.html")

    assert product.title == "JSON Product Title"
    assert product.description == "Complete AI overview details from the item data."


def test_scraped_json_metadata_array_is_supported():
    html = '''
    <html><head><script type="application/json">
    {"metadata":[
      {"property":"og:title","content":"Array Metadata Product Title"},
      {"name":"description","content":"Array metadata description fallback."}
    ]}
    </script></head><body><h1>Visible title</h1></body></html>
    '''
    product = parse_product_html(html, "https://www.aliexpress.com/item/789.html")

    assert product.title == "Array Metadata Product Title"
    assert product.description == "Array metadata description fallback."


def test_verification_screen_is_flagged_for_manual_review():
    assert looks_like_verification("https://www.aliexpress.com/", "<main>Slide to verify you are human</main>")
    assert not looks_like_verification("https://www.aliexpress.com/item/123.html", "<main>Portable reading lamp</main>")


def test_only_aliexpress_urls_are_allowed():
    assert validate_aliexpress_url("https://www.aliexpress.com/item/123.html").endswith("123.html")
    try:
        validate_aliexpress_url("https://example.com/product")
    except ExtractionError as error:
        assert "AliExpress" in str(error)
    else:
        raise AssertionError("A non-AliExpress URL should be rejected")
