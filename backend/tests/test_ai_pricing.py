from app.ai_pricing import get_model_rates


def test_known_model_rates_support_default_and_dated_model_ids():
    assert get_model_rates("gpt-4o-mini") == (0.15, 0.60)
    assert get_model_rates("gpt-4o-mini-2024-07-18") == (0.15, 0.60)
    assert get_model_rates("gpt-4.1-nano") == (0.10, 0.40)


def test_unknown_model_or_non_date_suffix_is_not_mispriced():
    assert get_model_rates("custom-deployment") is None
    assert get_model_rates("gpt-4o-mini-search-preview") is None
