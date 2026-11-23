from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.plan_limits import ensure_active
from app.services.pricing import DEFAULT_PLANS


def test_recommended_funeral_and_general_prices_are_the_defaults():
    plans = {row[1]: row for row in DEFAULT_PLANS}
    assert plans["funeral-beginner"][4:] == (89900, 5, 1, 6000, 15000)
    assert plans["funeral-standard"][4:] == (149900, 7, 2, 6000, 15000)
    assert plans["funeral-enterprise"][4:] == (249900, 15, 5, 6000, 15000)
    assert plans["general-startup"][4:] == (49900, 3, 1, 5000, 10000)
    assert plans["general-standard"][4:] == (99900, 6, 2, 5000, 10000)
    assert plans["general-enterprise"][4:] == (179900, 12, 5, 5000, 10000)


def test_active_trial_remains_available_until_its_end():
    business = SimpleNamespace(
        subscription_status="trial",
        trial_ends_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    assert ensure_active(business) is None


def test_expired_trial_is_blocked_with_payment_recovery_details():
    business = SimpleNamespace(
        subscription_status="trial",
        trial_ends_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    with pytest.raises(HTTPException) as caught:
        ensure_active(business)
    assert caught.value.status_code == 402
    assert caught.value.detail["code"] == "trial_expired"
    assert caught.value.detail["subscription_url"] == "/settings/subscription"


def test_naive_legacy_trial_end_is_interpreted_as_utc():
    business = SimpleNamespace(
        subscription_status="trial",
        trial_ends_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1),
    )
    with pytest.raises(HTTPException) as caught:
        ensure_active(business)
    assert caught.value.status_code == 402


def test_active_subscription_is_not_blocked_by_trial_timestamp():
    business = SimpleNamespace(
        subscription_status="active",
        trial_ends_at=datetime.now(timezone.utc) - timedelta(days=10),
    )
    assert ensure_active(business) is None
