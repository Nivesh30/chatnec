import pytest

from chatnec.metrics import metrics


@pytest.fixture(autouse=True)
def reset_metrics():
    metrics._counters.clear()
    yield
