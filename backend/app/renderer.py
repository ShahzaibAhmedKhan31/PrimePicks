from __future__ import annotations

from functools import lru_cache

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import get_template_dir
from app.models import ListingContent, ProductData


@lru_cache(maxsize=1)
def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(get_template_dir())),
        autoescape=select_autoescape(enabled_extensions=("html", "xml"), default_for_string=True),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_listing(product: ProductData, content: ListingContent) -> str:
    template = _environment().get_template("listing.html")
    selected_images = [image for image in product.images if image.selected][:8]
    return template.render(product=product, content=content, images=selected_images)
