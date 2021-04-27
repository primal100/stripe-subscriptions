import os

import pytest
import stripe
from datetime import datetime, timedelta

import subscriptions
from subscriptions import UserProtocol, CacheProtocol, User

from typing import Optional, Any, List

api_key = ''


@pytest.fixture(scope="session")
def stripe_subscription_product_url() -> str:
    return "http://localhost/paywall"


def pytest_addoption(parser):
    parser.addoption("--apikey", action="store", default=os.environ.get('STRIPE_TEST_SECRET_KEY'))


@pytest.fixture(scope="session", autouse=True)
def setup_stripe(pytestconfig):
    stripe.api_key = pytestconfig.getoption("apikey")


@pytest.fixture(scope="session")
def checkout_success_url() -> str:
    return "http://localhost"


@pytest.fixture(scope="session")
def checkout_cancel_url() -> str:
    return "http://localhost/cancel"


@pytest.fixture(scope="session")
def payment_method_types() -> List[str]:
    return ["card"]


@pytest.fixture
def user() -> UserProtocol:
    user = User(user_id=1, email='testuser@example.com')
    yield user
    if user.stripe_customer_id:
        subscriptions.delete_customer(user)


@pytest.fixture
def user_with_customer_id(user) -> UserProtocol:
    subscriptions.create_customer(user)
    return user


@pytest.fixture
def subscribed_user(user_with_customer_id, stripe_price_id) -> UserProtocol:
    subscriptions.tests.create_payment_method(user_with_customer_id)
    subscriptions.create_subscription(user_with_customer_id, stripe_price_id)
    return user_with_customer_id


@pytest.fixture(scope="session")
def stripe_subscription_product_id(stripe_subscription_product_url) -> str:
    products = stripe.Product.list(url=stripe_subscription_product_url, limit=1)
    if products:
        product = products['data'][0]
    else:
        product = stripe.Product.create(name="Gold Special", url=stripe_subscription_product_url)
    return product['id']


@pytest.fixture(scope="session")
def stripe_price_id(stripe_subscription_product_id) -> str:
    prices = stripe.Price.list(product=stripe_subscription_product_id, limit=1)
    if prices:
        price = prices.data[0]
    else:
        price = stripe.Price.create(
            unit_amount=129,
            currency="usd",
            recurring={"interval": "month"},
            product=stripe_subscription_product_id,
        )
    return price['id']


class Cache(CacheProtocol):
    expire_after = 60

    def __init__(self):
        self._data = {}

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


@pytest.fixture
def expected_subscription_prices() -> List:
    return []
