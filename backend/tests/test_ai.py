import asyncio
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.ai import LISTING_RESPONSE_SCHEMA, TokenUsage, generate_listing
from app.models import ListingContent, ProductData


def test_structured_ai_response_validates_all_expected_fields():
    payload = {
        "title": "Portable USB Reading Lamp Flexible Neck",
        "description": "A USB-powered lamp with an adjustable neck.",
        "features": ["Flexible neck for positioning", "USB power source"],
        "specifications": [{"name": "Power source", "value": "USB"}],
        "package_contents": ["1 lamp", "1 USB cable"],
        "usage_instructions": ["Charge before first use."],
        "warnings": ["Keep away from water."],
        "review_flags": ["Confirm the included cable length."],
    }
    result = ListingContent.model_validate_json(json.dumps(payload))

    assert result.title == payload["title"]
    assert result.warnings == payload["warnings"]
    assert set(LISTING_RESPONSE_SCHEMA["required"]) == set(payload)


def test_invalid_ai_response_is_rejected_instead_of_returned_as_html():
    payload = {
        "title": "T" * 81,
        "description": "Description",
        "features": ["Feature"],
        "specifications": [],
        "package_contents": [],
        "usage_instructions": [],
        "warnings": [],
        "review_flags": [],
    }
    with pytest.raises(ValidationError):
        ListingContent.model_validate(payload)


def test_reported_usage_is_captured_even_when_the_draft_fails_validation(monkeypatch):
    usage = SimpleNamespace(prompt_tokens=23, completion_tokens=11, total_tokens=34)

    async def create_completion(**_kwargs):
        return SimpleNamespace(
            usage=usage,
            choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))],
        )

    class FakeOpenAIClient:
        def __init__(self, **_kwargs):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=create_completion),
            )

        async def close(self):
            return None

    monkeypatch.setattr("app.ai.AsyncOpenAI", FakeOpenAIClient)
    recorded = []
    product = ProductData(
        source_url="https://www.aliexpress.com/item/123.html",
        title="Portable Reading Lamp",
        description="A USB-powered lamp.",
    )

    with pytest.raises(ValueError, match="did not pass validation"):
        asyncio.run(generate_listing(product, "sk-test", "gpt-4o-mini", on_usage=recorded.append))

    assert recorded == [TokenUsage(input_tokens=23, output_tokens=11, total_tokens=34)]
