from __future__ import annotations

from ipaddress import ip_address
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

ShortText = Annotated[str, Field(max_length=500)]


def _validate_remote_web_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
    except ValueError as error:
        raise ValueError("A valid public web URL is required") from error
    if parsed.scheme.lower() not in {"http", "https"} or not host:
        raise ValueError("A valid public HTTP or HTTPS URL is required")
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise ValueError("Local network URLs are not allowed")
    try:
        address = ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Local network URLs are not allowed")
    return value


class ProductAttribute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ShortText
    value: Annotated[str, Field(max_length=2_000)]


class ProductImage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: Annotated[str, Field(min_length=1, max_length=4_000)]
    alt: Annotated[str, Field(max_length=500)] = ""
    selected: bool = True

    @field_validator("url")
    @classmethod
    def image_url_must_be_public_web_url(cls, value: str) -> str:
        return _validate_remote_web_url(value)


class ProductData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_url: Annotated[str, Field(min_length=1, max_length=4_000)]
    title: Annotated[str, Field(max_length=1_500)] = ""
    description: Annotated[str, Field(max_length=30_000)] = ""
    specifications: list[ProductAttribute] = Field(default_factory=list, max_length=100)
    variations: list[Annotated[str, Field(max_length=500)]] = Field(default_factory=list, max_length=100)
    images: list[ProductImage] = Field(default_factory=list, max_length=40)
    package_contents: list[Annotated[str, Field(max_length=1_000)]] = Field(default_factory=list, max_length=50)
    usage_instructions: list[Annotated[str, Field(max_length=1_000)]] = Field(default_factory=list, max_length=50)
    warnings: list[Annotated[str, Field(max_length=1_000)]] = Field(default_factory=list, max_length=50)
    missing_info: list[Annotated[str, Field(max_length=500)]] = Field(default_factory=list, max_length=50)
    extraction_notes: list[Annotated[str, Field(max_length=500)]] = Field(default_factory=list, max_length=50)

    @field_validator("source_url")
    @classmethod
    def source_must_be_aliexpress(cls, value: str) -> str:
        value = _validate_remote_web_url(value)
        host = (urlsplit(value).hostname or "").lower().rstrip(".")
        if host not in {"aliexpress.com", "aliexpress.us"} and not host.endswith((".aliexpress.com", ".aliexpress.us")):
            raise ValueError("The product source must be an AliExpress URL")
        return value


class ListingContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, Field(min_length=1, max_length=80)]
    description: Annotated[str, Field(min_length=1, max_length=8_000)]
    features: list[Annotated[str, Field(max_length=500)]] = Field(default_factory=list, max_length=12)
    specifications: list[ProductAttribute] = Field(default_factory=list, max_length=100)
    package_contents: list[Annotated[str, Field(max_length=1_000)]] = Field(default_factory=list, max_length=50)
    usage_instructions: list[Annotated[str, Field(max_length=1_000)]] = Field(default_factory=list, max_length=50)
    warnings: list[Annotated[str, Field(max_length=1_000)]] = Field(default_factory=list, max_length=50)
    review_flags: list[Annotated[str, Field(max_length=500)]] = Field(default_factory=list, max_length=30)

    @field_validator("features", "package_contents", "usage_instructions", "warnings", "review_flags", mode="before")
    @classmethod
    def remove_empty_lines(cls, value: object) -> object:
        if isinstance(value, list):
            return [item for item in value if not isinstance(item, str) or item.strip()]
        return value

    @field_validator("specifications", mode="before")
    @classmethod
    def remove_incomplete_specifications(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        complete = []
        for item in value:
            if isinstance(item, dict):
                name, field_value = item.get("name"), item.get("value")
            else:
                name, field_value = getattr(item, "name", None), getattr(item, "value", None)
            if str(name or "").strip() and str(field_value or "").strip():
                complete.append(item)
        return complete


class ExtractionStartRequest(BaseModel):
    url: Annotated[str, Field(min_length=8, max_length=4_000)]


class HtmlExtractionRequest(BaseModel):
    """A product page the user loaded in the desktop app's built-in browser panel."""

    url: Annotated[str, Field(min_length=8, max_length=4_000)]
    html: Annotated[str, Field(min_length=1, max_length=25_000_000)]


class GenerateRequest(BaseModel):
    product: ProductData


class RenderRequest(BaseModel):
    product: ProductData
    content: ListingContent


class SaveListingRequest(RenderRequest):
    pass


class SettingsUpdate(BaseModel):
    api_key: Annotated[str, Field(max_length=500)] | None = None
    model: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    clear_api_key: bool = False

    @field_validator("model")
    @classmethod
    def model_name_is_safe(cls, value: str | None) -> str | None:
        if value is not None and any(character.isspace() for character in value.strip()):
            raise ValueError("Model name must not contain spaces")
        return value.strip() if value else value
