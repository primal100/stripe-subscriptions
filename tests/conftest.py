import pytest
from datetime import datetime, timedelta

import subscriptions
from subscriptions import UserProtocol, CacheProtocol, User

from typing import Optional, Any

api_key = ''
checkout_success_url = "http://localhost"
checkout_cancel_url = "http://localhost/cancelled"


@pytest.fixture(scope="session", autouse=True)
def setup_stripe():
    subscriptions.setup_stripe(api_key, checkout_success_url, checkout_cancel_url)


@pytest.fixture
def stripe_existing_customer_id() -> str:
    return ''


@pytest.fixture
def existing_user(stripe_existing_customer_id) -> UserProtocol:
    return User(user_id=1, email='testuser@example.com', stripe_customer_id=stripe_existing_customer_id)


@pytest.fixture
def new_user() -> UserProtocol:
    user = User(user_id=2, email='testuser2@example.com')
    yield user
    if user.stripe_customer_id:
        subscriptions.delete_customer(user)


@pytest.fixture
def stripe_subscription_product_id() -> str:
    return ''


@pytest.fixture
def stripe_yearly_price_id() -> str:
    return ''


@pytest.fixture
def stripe_monthly_price_id() -> str:
    return ''


class Cache(CacheProtocol):
    _data = {}
    expire_after = 60

    def get(self, key: str) -> Optional[Any]:
        result = self._data.get(key)
        if result:
            if result['expires'] > datetime.now():
                return result['value']
            del self._data[key]
        return None

    def set(self, key: str, value: Any) -> None:
        self._data[key] = {'value': value, 'expires': datetime.now() + timedelta(seconds=self.expire_after)}


@pytest.fixture
def cache() -> CacheProtocol:
    return Cache()
