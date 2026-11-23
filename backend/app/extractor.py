from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from app.config import get_data_dir
from app.models import ProductAttribute, ProductData, ProductImage

logger = logging.getLogger(__name__)
ProgressCallback = Callable[[str, str], Awaitable[None]]


class ExtractionError(Exception):
    """An expected, user-facing product extraction problem."""


def validate_aliexpress_url(url: str) -> str:
    value = url.strip()
    try:
        parsed = urlsplit(value)
    except ValueError as error:
        raise ExtractionError("Enter a valid AliExpress product URL.") from error
    host = (parsed.hostname or "").lower().rstrip(".")
    allowed = host in {"aliexpress.com", "aliexpress.us"} or host.endswith(
        (".aliexpress.com", ".aliexpress.us")
    )
    if parsed.scheme not in {"http", "https"} or not allowed:
        raise ExtractionError("Please enter a product URL from AliExpress.")
    if parsed.username or parsed.password:
        raise ExtractionError("This URL cannot be opened. Paste the public product link without sign-in details.")
    return value


def _text(node: Tag | None) -> str:
    if node is None:
        return ""
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()


def _clean_lines(value: str) -> list[str]:
    return [re.sub(r"\s+", " ", line).strip(" \t•·-\u2022") for line in value.splitlines() if line.strip()]


def _unique(values: list[str], limit: int = 100) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = re.sub(r"\s+", " ", value).strip()
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
        if len(result) >= limit:
            break
    return result


def _structured_products(soup: BeautifulSoup) -> list[dict[str, object]]:
    products: list[dict[str, object]] = []

    def visit(value: object) -> None:
        if isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            product_type = value.get("@type", [])
            types = product_type if isinstance(product_type, list) else [product_type]
            if any(str(item).rsplit("/", 1)[-1].casefold() == "product" for item in types):
                products.append(value)
            for child in value.values():
                if isinstance(child, (dict, list)):
                    visit(child)

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            visit(json.loads(script.string or script.get_text()))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return products


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _json_text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "\n".join(text for item in value if (text := _json_text(item)))
    if isinstance(value, dict):
        preferred = {
            "text",
            "content",
            "description",
            "overview",
            "summary",
            "value",
            "body",
            "paragraphs",
            "children",
            "items",
        }
        selected = [
            _json_text(item)
            for key, item in value.items()
            if _normalized_key(str(key)) in preferred
        ]
        selected = [text for text in selected if text]
        if selected:
            return "\n".join(selected)
        return "\n".join(text for item in value.values() if (text := _json_text(item)))
    return ""


def _embedded_metadata(soup: BeautifulSoup) -> dict[str, str]:
    """Read explicit Open Graph metadata and item AI-overview fields from JSON scripts."""
    titles: list[str] = []
    descriptions: list[str] = []
    overviews: list[str] = []
    metadata_keys = {"metadata", "metadatas", "metatags", "meta"}
    overview_keys = {
        "aioverviewofitem",
        "aioverviewitem",
        "itemaioverview",
        "aiitemoverview",
        "aioverview",
        "aiitemsummary",
    }
    overview_labels = {"aioverviewofitem", "aioverviewitem", "aioverview"}

    def visit(value: object, in_metadata: bool = False) -> None:
        if isinstance(value, list):
            for item in value:
                visit(item, in_metadata)
            return
        if not isinstance(value, dict):
            return

        current_metadata = in_metadata or any(
            _normalized_key(str(key)) in metadata_keys and isinstance(item, (dict, list))
            for key, item in value.items()
        )
        normalized_items = {_normalized_key(str(key)): (key, item) for key, item in value.items()}
        for normalized, (_, item) in normalized_items.items():
            if normalized in {"ogtitle", "opengraphtitle"}:
                text = _json_text(item)
                if text:
                    titles.append(text)
            elif normalized == "ogdescription" or (current_metadata and normalized == "description"):
                text = _json_text(item)
                if text:
                    descriptions.append(text)
            elif normalized in overview_keys:
                text = _json_text(item)
                if text:
                    overviews.append(text)

        if current_metadata:
            metadata_name = next(
                (
                    str(item).strip()
                    for key, item in value.items()
                    if _normalized_key(str(key)) in {"property", "name", "key"}
                    and isinstance(item, str)
                ),
                "",
            )
            metadata_value = next(
                (item for key, item in value.items() if _normalized_key(str(key)) in {"content", "value"}),
                "",
            )
            normalized_name = _normalized_key(metadata_name)
            if normalized_name in {"ogtitle", "opengraphtitle"}:
                text = _json_text(metadata_value)
                if text:
                    titles.append(text)
            elif normalized_name in {"description", "ogdescription"}:
                text = _json_text(metadata_value)
                if text:
                    descriptions.append(text)

        heading = next(
            (
                str(item).strip()
                for normalized, (_, item) in normalized_items.items()
                if normalized in {"title", "heading", "label", "name"} and isinstance(item, str)
            ),
            "",
        )
        if _normalized_key(heading) in overview_labels:
            overview_fields = {
                key: item
                for key, item in value.items()
                if _normalized_key(str(key)) not in {"title", "heading", "label", "name"}
            }
            text = _json_text(overview_fields)
            if text:
                overviews.append(text)

        for key, item in value.items():
            if isinstance(item, (dict, list)):
                visit(item, current_metadata or _normalized_key(str(key)) in metadata_keys)

    for script in soup.find_all("script"):
        script_type = str(script.get("type", "")).casefold()
        if "json" not in script_type and script.get("id") != "__NEXT_DATA__":
            continue
        raw = script.string or script.get_text()
        if not raw or len(raw) > 5_000_000:
            continue
        try:
            visit(json.loads(raw))
        except (json.JSONDecodeError, TypeError, ValueError, RecursionError):
            continue

    return {
        "og_title": titles[0] if titles else "",
        "description": max(descriptions, key=len) if descriptions else "",
        "ai_overview": max(overviews, key=len) if overviews else "",
    }


def _ai_overview_from_dom(soup: BeautifulSoup) -> str:
    label_pattern = re.compile(r"^\s*AI\s+Overview\s+of\s+(?:the\s+)?Item\s*[:：—-]?\s*(.*)$", re.I)
    candidates: list[str] = []
    for node in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "strong", "b", "span", "div", "p"]):
        if not label_pattern.match(_text(node)):
            continue
        for ancestor in node.parents:
            if not isinstance(ancestor, Tag) or ancestor.name in {"body", "html"}:
                continue
            raw_lines = ancestor.get_text("\n", strip=True).splitlines()
            lines = [re.sub(r"\s+", " ", line).strip() for line in raw_lines if line.strip()]
            body: list[str] = []
            found_label = False
            for line in lines:
                match = label_pattern.match(line)
                if not found_label:
                    if match:
                        found_label = True
                        if match.group(1).strip():
                            body.append(match.group(1).strip())
                    continue
                body.append(line)
            overview = "\n".join(body).strip()
            if found_label and len(overview) > 30 and len(overview) <= 100_000:
                candidates.append(overview)
    return min(candidates, key=len) if candidates else ""


def _description(soup: BeautifulSoup) -> str:
    selectors = [
        "#product-description",
        "[data-pl='product-description']",
        "[class*='product-description']",
        "[id*='description']",
        "[class*='description']",
    ]
    candidates: list[str] = []
    for selector in selectors:
        for node in soup.select(selector):
            text = node.get_text("\n", strip=True)
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
            if len(text) > 30:
                candidates.append(text)
    if not candidates:
        return ""
    # Prefer the longest product-description region, not the entire page chrome.
    return max(candidates, key=len)


def _specifications(soup: BeautifulSoup) -> list[ProductAttribute]:
    pairs: list[ProductAttribute] = []
    seen: set[tuple[str, str]] = set()
    for table in soup.select("table"):
        for row in table.select("tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            if len(cells) < 2:
                cells = row.find_all(["th", "td"])
            if len(cells) < 2:
                continue
            name, value = _text(cells[0]), _text(cells[1])
            if not name or not value or len(name) > 150 or len(value) > 2_000:
                continue
            key = (name.casefold(), value.casefold())
            if key not in seen:
                seen.add(key)
                pairs.append(ProductAttribute(name=name, value=value))

    # AliExpress frequently renders attribute/value pairs as divs rather than a table.
    if not pairs:
        for node in soup.select("[class*='specification'] li, [class*='attribute'] li, [class*='product-prop'] li"):
            text = _text(node)
            if ":" in text:
                name, value = text.split(":", 1)
                if name.strip() and value.strip():
                    pairs.append(ProductAttribute(name=name.strip(), value=value.strip()[:2_000]))
    return pairs[:100]


def _structured_specifications(product: dict[str, object] | None) -> list[ProductAttribute]:
    if not product:
        return []
    raw = product.get("additionalProperty", [])
    properties = raw if isinstance(raw, list) else [raw]
    result: list[ProductAttribute] = []
    for item in properties:
        if not isinstance(item, dict):
            continue
        name, value = item.get("name"), item.get("value")
        if name is not None and value is not None and str(name).strip() and str(value).strip():
            result.append(ProductAttribute(name=str(name)[:500], value=str(value)[:2_000]))
    return result[:100]


def _structured_images(product: dict[str, object] | None) -> list[str]:
    if not product:
        return []
    raw = product.get("image", [])
    values = raw if isinstance(raw, list) else [raw]
    urls: list[str] = []
    for item in values:
        if isinstance(item, str):
            urls.append(item)
        elif isinstance(item, dict) and item.get("url"):
            urls.append(str(item["url"]))
    return _unique(urls, limit=40)


def _variations(soup: BeautifulSoup) -> list[str]:
    found: list[str] = []
    for select in soup.select("select"):
        label = ""
        select_id = select.get("id")
        if select_id:
            label_node = soup.find("label", attrs={"for": select_id})
            label = _text(label_node)
        label = label or str(select.get("name", "")).replace("_", " ").strip()
        values = [option.get_text(" ", strip=True) for option in select.select("option")]
        values = [item for item in values if item and item.lower() not in {"select", "please select"}]
        if values:
            found.append(f"{label + ': ' if label else ''}{', '.join(values[:20])}")

    for node in soup.select("[class*='sku'], [class*='variant'], [class*='property-item'], [class*='sku-item']"):
        text = _text(node)
        if text and len(text) < 300:
            found.append(text)

    return _unique(found, limit=100)


def _images(
    soup: BeautifulSoup,
    base_url: str,
    title: str,
    structured_images: list[str] | None = None,
) -> list[ProductImage]:
    values: list[ProductImage] = []
    seen: set[str] = set()
    if meta := soup.find("meta", property="og:image"):
        src = meta.get("content")
        if src:
            absolute = urljoin(base_url, str(src))
            if urlsplit(absolute).scheme in {"https", "http"}:
                try:
                    values.append(ProductImage(url=absolute, alt=title, selected=True))
                except ValueError:
                    pass
                else:
                    seen.add(absolute)

    for src in structured_images or []:
        absolute = urljoin(base_url, src)
        if urlsplit(absolute).scheme in {"https", "http"} and absolute not in seen:
            try:
                values.append(ProductImage(url=absolute, alt=title, selected=len(values) < 8))
            except ValueError:
                continue
            seen.add(absolute)

    for image in soup.find_all("img"):
        src = image.get("data-src") or image.get("data-lazy-src") or image.get("src")
        if not src and image.get("srcset"):
            src = str(image["srcset"]).split(",")[-1].strip().split(" ")[0]
        if not src or str(src).startswith(("data:", "blob:")):
            continue
        absolute = urljoin(base_url, str(src))
        parsed = urlsplit(absolute)
        if parsed.scheme not in {"https", "http"} or absolute in seen:
            continue
        alt = str(image.get("alt") or title)
        source_text = f"{absolute} {alt}".lower()
        if any(term in source_text for term in ("logo", "avatar", "icon", "flag", "payment")):
            continue
        width = image.get("width")
        height = image.get("height")
        try:
            if width and int(width) < 80:
                continue
            if height and int(height) < 80:
                continue
        except (TypeError, ValueError):
            pass
        try:
            values.append(ProductImage(url=absolute, alt=alt[:500], selected=len(values) < 8))
        except ValueError:
            continue
        seen.add(absolute)
        if len(values) >= 40:
            break
    return values


def _section_lines(lines: list[str], pattern: re.Pattern[str], max_items: int = 20) -> list[str]:
    matches: list[str] = []
    capture = False
    boundary = re.compile(
        r"^\s*(warnings?|caution|instructions?|usage|directions|package\s*(?:includes?|contents?)|what'?s\s+in\s+the\s+box|you\s+will\s+receive)\s*[:：]",
        re.I,
    )
    for line in lines:
        is_target = bool(pattern.search(line))
        if capture and boundary.search(line) and not is_target:
            break
        if is_target:
            tail = re.split(r"[:：]", line, maxsplit=1)
            if len(tail) == 2 and tail[1].strip():
                matches.append(tail[1].strip())
            capture = True
            continue
        if capture:
            if len(line) < 100 and (line.endswith(":") or re.match(r"^[A-Z][A-Za-z /&-]{2,40}$", line)):
                break
            matches.append(line)
            if len(matches) >= max_items:
                break
    return _unique(matches, max_items)


def _meta_content(soup: BeautifulSoup, attribute: str, value: str) -> str:
    node = soup.find("meta", attrs={attribute: value})
    return str(node.get("content", "")).strip() if node else ""


def parse_product_html(html: str, source_url: str) -> ProductData:
    soup = BeautifulSoup(html, "html.parser")
    structured_products = _structured_products(soup)
    structured = structured_products[0] if structured_products else None
    embedded_metadata = _embedded_metadata(soup)

    # Prefer scraped Open Graph metadata over a possibly generic visible heading.
    og_title = (
        embedded_metadata["og_title"]
        or _meta_content(soup, "property", "og:title")
        or _meta_content(soup, "name", "og:title")
    )
    title = og_title
    if not title:
        for selector in ["h1", "[data-pl='product-title']", "[class*='product-title']"]:
            node = soup.select_one(selector)
            if _text(node):
                title = _text(node)
                break
    if not title:
        title = _meta_content(soup, "name", "title")
    if not title and structured and structured.get("name"):
        title = str(structured["name"]).strip()
    if not title and soup.title:
        title = _text(soup.title)

    ai_overview = embedded_metadata["ai_overview"] or _ai_overview_from_dom(soup)
    meta_description = (
        embedded_metadata["description"]
        or _meta_content(soup, "name", "description")
        or _meta_content(soup, "property", "og:description")
        or _meta_content(soup, "name", "og:description")
    )
    # Prefer a complete item overview, then the metadata description, before wider DOM/JSON-LD fallbacks.
    description = ai_overview or meta_description or _description(soup)
    if not description and structured and structured.get("description"):
        description = str(structured["description"]).strip()
    description_truncated = len(description) > 30_000
    description = description[:30_000]
    specifications = _specifications(soup) or _structured_specifications(structured)
    variations = _variations(soup)
    images = _images(soup, source_url, title, _structured_images(structured))
    lines = _clean_lines(description)
    package = _section_lines(
        lines,
        re.compile(r"\b(package\s*(includes?|contents?)|what'?s\s+in\s+the\s+box|you\s+will\s+receive)\b", re.I),
    )
    instructions = _section_lines(
        lines,
        re.compile(r"\b(how\s+to\s+(use|install)|instructions?|usage|directions|care\s+instructions?)\b", re.I),
    )
    warnings = _section_lines(
        lines,
        re.compile(r"\b(warnings?|caution|safety\s+information|keep\s+away|not\s+suitable)\b", re.I),
    )
    if not warnings:
        warnings = [line for line in lines if re.search(r"\b(warning|caution|hazard|keep out of reach|small parts)\b", line, re.I)][:20]

    missing: list[str] = []
    if not title:
        missing.append("Product title could not be detected. Add or confirm it before generating.")
    if not description:
        missing.append("A detailed product description was not detected. Review the source page and add details if needed.")
    if not specifications:
        missing.append("No product specifications were detected. Confirm material, size, compatibility, and other relevant details.")
    if not images:
        missing.append("No product images were detected. Select or add images before finalizing.")
    notes: list[str] = []
    if description_truncated:
        notes.append("The product description exceeded the extraction limit. Review the full source page before publishing.")
    elif description and len(description) < 120:
        notes.append("Only a short product summary was detected. Confirm the full description and limitations on the source page.")
    if not variations:
        notes.append("No selectable variations were detected. Confirm size, color, and quantity options on the source page.")
    if not package:
        notes.append("Package contents were not clearly identified on the source page; confirm before publishing.")
    return ProductData(
        source_url=source_url,
        title=title[:1_500],
        description=description,
        specifications=specifications,
        variations=variations,
        images=images,
        package_contents=package,
        usage_instructions=instructions,
        warnings=warnings,
        missing_info=missing,
        extraction_notes=notes,
    )


_CHALLENGE_RE = re.compile(
    r"(verify\s+you(?:'re|\s+are)\s+human|security\s+verification|captcha|slide\s+to\s+verify|unusual\s+traffic|robot\s+check|verify\s+your\s+account"
    # AliExpress/Alibaba block page: "We have detected unusual/inappropriate network activity"
    r"|(?:unusual|inappropriate|abnormal|suspicious)\s+(?:network\s+)?(?:activity|traffic|behaviou?r)"
    r"|please\s+slide\s+to\s+verify|drag\s+the\s+slider)",
    re.I,
)
# AliExpress serves its block page from /_____tmd_____/punish (x5sec/baxia challenge).
_CHALLENGE_URL_RE = re.compile(r"captcha|verify|security|punish|_____tmd_____|x5sec|baxia", re.I)


def looks_like_verification(url: str, html: str) -> bool:
    if _CHALLENGE_URL_RE.search(url):
        return True
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)[:20_000]
    return bool(_CHALLENGE_RE.search(text))


async def _frame_is_shown_to_user(frame: Any) -> bool:
    """True when an iframe is visible and large enough to be a challenge the user can act on.

    Product pages routinely contain hidden challenge frames (an invisible Google reCAPTCHA
    badge, background "punish" frames for recommendation widgets). Only frames the user can
    actually see should pause extraction; otherwise the user is asked to solve nothing.
    """
    try:
        element = await frame.frame_element()
        if not await element.is_visible():
            return False
        box = await element.bounding_box()
    except Exception:
        return False
    return bool(box and box["width"] >= 200 and box["height"] >= 120)


async def page_needs_manual_verification(page: Any) -> bool:
    if looks_like_verification(page.url, await page.content()):
        return True
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        try:
            if looks_like_verification(frame.url, await frame.content()) and await _frame_is_shown_to_user(frame):
                return True
        except Exception:
            continue
    return False


# Prefer the browsers already installed on Windows (Edge ships with Windows 10/11).
# A regular Edge/Chrome build is challenged less often by AliExpress than Playwright's
# test Chromium, and it means the installer does not need to bundle a browser.
# "chromium" (Playwright's own build) remains as a developer fallback.
BROWSER_CHANNELS: tuple[str, ...] = ("msedge", "chrome", "chromium")


async def _launch_browser_context(playwright: Any) -> Any:
    last_error: Exception | None = None
    for channel in BROWSER_CHANNELS:
        # Edge, Chrome and Chromium profiles are not interchangeable, so keep one per browser.
        profile_dir = get_data_dir() / f"browser-profile-{channel}"
        options: dict[str, Any] = {
            "headless": False,
            "locale": "en-US",
            "viewport": {"width": 1440, "height": 950},
        }
        if channel != "chromium":
            options["channel"] = channel
        try:
            context = await playwright.chromium.launch_persistent_context(str(profile_dir), **options)
        except Exception as error:  # browser not installed or failed to start; try the next one
            logger.info("Could not start %s browser: %s", channel, type(error).__name__)
            last_error = error
            continue
        logger.info("Using %s browser for extraction", channel)
        return context
    raise ExtractionError(
        "Microsoft Edge could not be opened. Make sure Microsoft Edge is installed and up to date, then try again."
    ) from last_error


async def extract_product(
    url: str,
    report: ProgressCallback,
    continue_event: asyncio.Event,
) -> ProductData:
    """Open a visible browser window (Edge by default) and extract public, rendered page content.

    Verification is deliberately left to the user. This routine waits while the
    browser stays open and resumes only when the UI signals that the user is done.
    """
    url = validate_aliexpress_url(url)
    await report("opening", "Opening the product page in Microsoft Edge...")
    try:
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            context = await _launch_browser_context(playwright)
            # Edge's startup tab can be taken over by its first-run/welcome flow on a new
            # profile (navigation then fails with "frame was detached"), so use a fresh tab.
            startup_pages = list(context.pages)
            page = await context.new_page()
            for startup_page in startup_pages:
                try:
                    await startup_page.close()
                except Exception:
                    pass
            try:
                await report("waiting", "Waiting for the product page to load...")
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                except PlaywrightTimeoutError:
                    if page.url == "about:blank":
                        raise ExtractionError("AliExpress did not load. Check your connection and try again.")
                    logger.info("AliExpress page continued after navigation timeout")
                await page.wait_for_timeout(5_000)
                final_host = (urlsplit(page.url).hostname or "").lower()
                if not (final_host.endswith(".aliexpress.com") or final_host in {"aliexpress.com", "aliexpress.us"} or final_host.endswith(".aliexpress.us")):
                    raise ExtractionError("AliExpress redirected to an unexpected page. Please reopen the original product link.")

                while True:
                    if not await page_needs_manual_verification(page):
                        break
                    await report(
                        "verification_required",
                        "AliExpress is asking for a human verification. Complete it in the Microsoft Edge window, then return here and choose Continue.",
                    )
                    await continue_event.wait()
                    continue_event.clear()
                    await report("waiting", "Checking the product page after verification...")
                    await page.wait_for_timeout(3_000)

                await report("extracting", "Extracting product details and images...")
                # Some product pages populate their gallery and options after initial DOM load.
                await page.wait_for_timeout(1_500)
                if await page_needs_manual_verification(page):
                    raise ExtractionError(
                        "AliExpress is still showing a verification page. Complete it in the browser window, then try again."
                    )
                html = await page.content()
                product = parse_product_html(html, page.url)
                if not product.title.strip() and not product.images:
                    raise ExtractionError(
                        "The product page did not load fully (no title or images were found). "
                        "If AliExpress showed a verification or warning, complete it in the browser window and try again."
                    )
                await report("completed", "Product information extracted. Review the details before generating copy.")
                return product
            finally:
                await context.close()
    except ExtractionError:
        raise
    except asyncio.CancelledError:
        raise
    except Exception as error:
        logger.exception("AliExpress extraction failed (%s)", type(error).__name__)
        name = type(error).__name__
        if name in {"Error", "TargetClosedError"}:
            raise ExtractionError("The product browser closed before extraction finished. Try again and keep the browser window open.") from error
        raise ExtractionError("We couldn't read this AliExpress page. Check the link, connection, and any verification shown in the browser window, then try again.") from error
