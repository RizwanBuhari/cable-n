import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.update({
    'APP_ENV': 'development', 'AI_ENABLED': 'false', 'CALC_RATE_PER_MINUTE': '100000',
    'REPORT_RATE_PER_MINUTE': '100000', 'VALIDATION_RATE_PER_MINUTE': '100000',
    'PREMIUM_SECRET': 'test-premium-secret',
})

import pytest  # noqa: E402


@pytest.fixture(scope='session')
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c
