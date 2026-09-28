"""Shared fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ns_departures.api import BASE_URL

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def ns_api(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    aioclient_mock.get(f"{BASE_URL}/v2/stations", json=load_fixture("stations.json"))
    aioclient_mock.get(f"{BASE_URL}/v3/trips", json=load_fixture("trips.json"))
    return aioclient_mock
