import json

import pytest
from pydantic import ValidationError

from app.ai import LISTING_RESPONSE_SCHEMA
from app.models import ListingContent


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
