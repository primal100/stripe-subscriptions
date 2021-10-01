import os

import sys
import pytest
import stripe
from stripe.error import InvalidRequestError
from datetime import datetime, timedelta

import subscriptions
from subscriptions import UserProtocol, User

from typing import Optional, Any, List, Dict

api_key = ''
python_version = sys.version_info
ci_string = f'{os.name}-{python_version.major}{python_version.minor}'


def pytest_addoption(parser):
    parser.addoption("--apikey", action="store", default=os.environ.get('STRIPE_TEST_SECRET_KEY'))


@pytest.fixture(scope="session")
def stripe_subscription_product_url() -> str:
    return "http://localhost/paywall"


@pytest.fixture(scope="session")
def stripe_unsubscribed_product_url() -> str:
    return "http://localhost/second_paywall"


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
def user_email() -> str:
    return f'stripe-subscriptions-{ci_string}@example.com'


@pytest.fixture
def user(user_email) -> UserProtocol:
    user = User(user_id=1, email=user_email)
    yield user
    if user.stripe_customer_id:
        try:
            subscriptions.delete_customer(user)
        except InvalidRequestError:
            pass


@pytest.fixture(params=[None, "user"])
def none_or_user(request, user) -> Optional[UserProtocol]:
    if not request.param:
        return None
    return user


@pytest.fixture
def wrong_customer_id() -> UserProtocol:
    user = User(
        2,
        "abc@yahoo.com",
        'cus_1234567890ABCD'
    )
    return user


@pytest.fixture
def user_with_customer_id(user, user_email) -> UserProtocol:
    customers = stripe.Customer.list(email=user_email)
    for customer in customers:
        stripe.Customer.delete(customer)
    subscriptions.create_customer(user, description="stripe-subscriptions test runner user")
    return user


@pytest.fixture(params=["no-customer-id", "with-customer-id"])
def user_with_and_without_customer_id(request, user) -> UserProtocol:
    if request.param == "no-customer-id":
        return user
    subscriptions.create_customer(user, description="stripe-subscriptions test runner user")
    return user


@pytest.fixture(params=["no-user", "no-customer-id", "with-customer-id"])
def no_user_and_user_with_and_without_customer_id(request, user) -> Optional[UserProtocol]:
    if request.param == "no-user":
        return None
    elif request.param == "no-customer-id":
        return user
    subscriptions.create_customer(user, description="stripe-subscriptions test runner user")
    return user


@pytest.fixture
def payment_method_for_customer(user_with_customer_id) -> stripe.PaymentMethod:
    return subscriptions.tests.create_payment_method_for_customer(user_with_customer_id)


@pytest.fixture
def default_payment_method_for_customer(user_with_customer_id) -> stripe.PaymentMethod:
    return subscriptions.tests.create_default_payment_method_for_customer(user_with_customer_id)


@pytest.fixture
def payment_method_saved(user_with_customer_id, payment_method_for_customer) -> stripe.PaymentMethod:
    payment_method_for_customer['customer'] = user_with_customer_id.stripe_customer_id
    payment_method_for_customer['card']['checks']['cvc_check'] = "pass"
    return payment_method_for_customer


@pytest.fixture
def default_payment_method_saved(user_with_customer_id, default_payment_method_for_customer) -> stripe.PaymentMethod:
    default_payment_method_for_customer['customer'] = user_with_customer_id.stripe_customer_id
    default_payment_method_for_customer['card']['checks']['cvc_check'] = "pass"
    return default_payment_method_for_customer


@pytest.fixture
def subscription(user_with_customer_id, default_payment_method_for_customer, stripe_price_id) -> stripe.Subscription:
    return subscriptions.create_subscription(user_with_customer_id, stripe_price_id)


@pytest.fixture
def non_existing_payment_method_id() -> str:
    return "pm_ABCDEFGH123456"


@pytest.fixture
def non_existing_subscription_id() -> str:
    return "sub_ABCDEFGH123456"


@pytest.fixture(scope="session")
def subscribed_product_name() -> str:
    return 'Gold'


@pytest.fixture(scope="session")
def stripe_subscription_product_id(stripe_subscription_product_url, subscribed_product_name) -> str:
    products = stripe.Product.list(url=stripe_subscription_product_url, active=True, limit=1)
    if products:
        product = products['data'][0]
    else:
        product = stripe.Product.create(name=subscribed_product_name, url=stripe_subscription_product_url)
    return product['id']


@pytest.fixture(scope="session")
def stripe_price_currency() -> str:
    return "usd"


@pytest.fixture(scope="session")
def unsubscribed_product_name() -> str:
    return 'Silver'


@pytest.fixture(scope="session")
def stripe_unsubscribed_product_id(unsubscribed_product_name, stripe_unsubscribed_product_url) -> str:
    products = stripe.Product.list(url=stripe_unsubscribed_product_url, active=True, limit=1)
    if products:
        product = products['data'][0]
    else:
        product = stripe.Product.create(name=unsubscribed_product_name, url=stripe_unsubscribed_product_url)
    return product['id']


@pytest.fixture(scope="session")
def stripe_price_id(stripe_subscription_product_id) -> str:
    prices = stripe.Price.list(product=stripe_subscription_product_id, active=True, limit=1)
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


@pytest.fixture(scope="session")
def stripe_unsubscribed_price_id(stripe_unsubscribed_product_id) -> str:
    prices = stripe.Price.list(product=stripe_unsubscribed_product_id, active=True, limit=1)
    if prices:
        price = prices.data[0]
    else:
        price = stripe.Price.create(
            unit_amount=9999,
            currency="usd",
            recurring={"interval": "year"},
            product=stripe_unsubscribed_product_id,
        )
    return price['id']


@pytest.fixture
def subscription_current_period_end(subscription):
    return subscription['current_period_end']


@pytest.fixture
def expected_subscription_prices(stripe_subscription_product_id, stripe_price_id, stripe_price_currency, subscription_current_period_end) -> List:
    return [
        {'id': stripe_price_id,
         'recurring': {
              "aggregate_usage": None,
              "interval": "month",
              "interval_count": 1,
              "trial_period_days": None,
              "usage_type": "licensed",
         },
         'type': 'recurring',
         'currency': stripe_price_currency,
         'unit_amount': 129,
         'unit_amount_decimal': '129',
         'nickname': None,
         'metadata': {},
         'product': stripe_subscription_product_id,
         'subscription_info': {'subscribed': True, 'cancel_at': None, 'current_period_end': subscription_current_period_end}}]



@pytest.fixture
def expected_subscription_prices_unsubscribed(stripe_subscription_product_id, stripe_price_id,
                                              stripe_price_currency) -> List:
    return [
        {'id': stripe_price_id,
         'recurring': {
              "aggregate_usage": None,
              "interval": "month",
              "interval_count": 1,
              "trial_period_days": None,
              "usage_type": "licensed",
         },
         'type': 'recurring',
         'currency': stripe_price_currency,
         'unit_amount': 129,
         'unit_amount_decimal': '129',
         'nickname': None,
         'metadata': {},
         'product': stripe_subscription_product_id,
         'subscription_info': {'subscribed': False, 'cancel_at': None, 'current_period_end': None}}]


@pytest.fixture
def expected_subscription_products_and_prices(stripe_subscription_product_id, stripe_price_id,
                                              subscribed_product_name, stripe_unsubscribed_product_id,
                                              unsubscribed_product_name, stripe_unsubscribed_price_id,
                                              stripe_subscription_product_url,
                                              stripe_unsubscribed_product_url,
                                              stripe_price_currency, subscription_current_period_end) -> List:
    return [
        {'id': stripe_unsubscribed_product_id,
         'images': [],
         'metadata': {},
         'name': unsubscribed_product_name,
            'prices': [{'currency': stripe_price_currency,
                  'id': stripe_unsubscribed_price_id,
                  'metadata': {},
                  'nickname': None,
                  'recurring': {'aggregate_usage': None,
                                'interval': 'year',
                                'interval_count': 1,
                                'trial_period_days': None,
                                'usage_type': 'licensed'},
                  'subscription_info': {'cancel_at': None, 'current_period_end': None, 'subscribed': False},
                  'type': 'recurring',
                  'unit_amount': 9999,
                  'unit_amount_decimal': '9999'}],
         'shippable': None,
         'subscription_info': {'cancel_at': None, 'current_period_end': None, 'subscribed': False},
         'type': 'service',
         'unit_label': None,
         'url': stripe_unsubscribed_product_url},
        {'id': stripe_subscription_product_id,
         'images': [],
         'type': 'service',
         'name': subscribed_product_name,
         'shippable': None,
         'unit_label': None,
         'url': stripe_subscription_product_url,
         'metadata': {},
         'prices': [{'id': stripe_price_id,
                     'recurring': {
                      "aggregate_usage": None,
                      "interval": "month",
                      "interval_count": 1,
                      "trial_period_days": None,
                      "usage_type": "licensed"
                    },
                     'type': 'recurring',
                     'currency': stripe_price_currency,
                     'unit_amount': 129,
                     'unit_amount_decimal': '129',
                     'nickname': None,
                     'metadata': {},
                     'subscription_info': {'subscribed': True, 'current_period_end': subscription_current_period_end, 'cancel_at': None}}],
         'subscription_info': {'subscribed': True, 'current_period_end': subscription_current_period_end, 'cancel_at': None}}
    ]


@pytest.fixture
def expected_subscription_products_and_prices_unsubscribed(stripe_subscription_product_id, stripe_price_id,
                                                           subscribed_product_name, stripe_unsubscribed_product_id,
                                                           unsubscribed_product_name, stripe_unsubscribed_price_id,
                                                           stripe_subscription_product_url,
                                                           stripe_unsubscribed_product_url,
                                                           stripe_price_currency) -> List:
    return [
        {'id': stripe_unsubscribed_product_id,
         'images': [],
         'metadata': {},
         'name': unsubscribed_product_name,
            'prices': [{'currency': stripe_price_currency,
                  'id': stripe_unsubscribed_price_id,
                  'metadata': {},
                  'nickname': None,
                  'recurring': {'aggregate_usage': None,
                                'interval': 'year',
                                'interval_count': 1,
                                'trial_period_days': None,
                                'usage_type': 'licensed'},
                  'subscription_info': {'cancel_at': None, 'current_period_end': None, 'subscribed': False},
                  'type': 'recurring',
                  'unit_amount': 9999,
                  'unit_amount_decimal': '9999'}],
         'shippable': None,
         'subscription_info': {'cancel_at': None, 'current_period_end': None, 'subscribed': False},
         'type': 'service',
         'unit_label': None,
         'url': stripe_unsubscribed_product_url},
        {'id': stripe_subscription_product_id,
         'images': [],
         'type': 'service',
         'name': subscribed_product_name,
         'shippable': None,
         'unit_label': None,
         'url': stripe_subscription_product_url,
         'metadata': {},
         'prices': [{'id': stripe_price_id,
                     'recurring': {
                      "aggregate_usage": None,
                      "interval": "month",
                      "interval_count": 1,
                      "trial_period_days": None,
                      "usage_type": "licensed"
                    },
                     'type': 'recurring',
                     'currency': stripe_price_currency,
                     'unit_amount': 129,
                     'unit_amount_decimal': '129',
                     'nickname': None,
                     'metadata': {},
                     'subscription_info': {'subscribed': False, 'current_period_end': None,'cancel_at': None}}],
         'subscription_info': {'subscribed': False, 'current_period_end': None,'cancel_at': None}}
    ]
