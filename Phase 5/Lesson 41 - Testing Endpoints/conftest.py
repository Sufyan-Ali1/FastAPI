"""
conftest.py - shared pytest fixtures.

pytest auto-discovers fixtures here and makes them available to every test file
WITHOUT importing them. The `client` fixture clears dependency overrides after
each test so tests never contaminate one another.
"""

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    with TestClient(app) as c:      # setup (runs lifespan if any)
        yield c                     # the test runs here
    # teardown - runs even if the test failed:
    app.dependency_overrides.clear()  # <-- critical: reset overrides every test
