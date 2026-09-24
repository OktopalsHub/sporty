"""The web UI offers 50/100 games; generator request models must accept both."""

import pytest
from pydantic import ValidationError

from app.api.routes.generators import GeneratorRequest
from app.api.routes.weekly_safe import WeeklySafeRequest

MODELS = [GeneratorRequest, WeeklySafeRequest]


@pytest.mark.parametrize("model", MODELS)
def test_generator_accepts_ui_page_sizes(model):
    assert model(page=1, page_size=50, hours=24).page_size == 50
    assert model(page=1, page_size=100, hours=24).page_size == 100


@pytest.mark.parametrize("model", MODELS)
def test_generator_rejects_page_size_above_100(model):
    with pytest.raises(ValidationError):
        model(page=1, page_size=101, hours=24)
