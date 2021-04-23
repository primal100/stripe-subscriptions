import stripe
from .decorators import customer_id_required
from .exceptions import StripeCustomerIdRequired
from . import tests
from .types import UserProtocol, CacheProtocol

from typing import Any, Dict, List, Optional, Tuple


version = "1.0.0"
app_name = 'stripe-subscriptions'
app_url = "https://github.com/primal100/stripe-subscriptions"


class Settings:
    checkout_success_url = None
    checkout_cancel_url = None


settings = Settings()


class User(UserProtocol):
    def __init__(self, user_id: Any, email: str, stripe_customer_id: Optional[str] = None):
        self.id = user_id
        self.email = email
        self.stripe_customer_id = stripe_customer_id


def setup_stripe(api_key: str, stripe_checkout_success_url = None, stripe_checkout_cancel_url: str = None,
                 set_app_info: bool = True) -> None:
    stripe.api_key = api_key
    settings.checkout_success_url = stripe_checkout_success_url
    settings.checkout_cancel_url = stripe_checkout_cancel_url
    if set_app_info:
        stripe.set_app_info(app_name, version=version, url=app_url)


def create_customer(user: UserProtocol, metadata: Optional[Dict[str, Any]] = None) -> stripe.Customer:
    metadata = metadata or {}
    metadata ['id'] = user.id
    customer = stripe.Customer.create(email=user.email, name=str(user), metadata=metadata)
    user.stripe_customer_id = customer['id']
    return customer


@customer_id_required
def create_checkout(user: UserProtocol, mode: str, line_items: List[Dict[str, Any]]) -> stripe.checkout.Session:
    checkout_session = stripe.checkout.Session.create(
        client_reference_id=user.id,
        success_url=settings.checkout_success_url,
        cancel_url=settings.checkout_cancel_url,
        customer=user.stripe_customer_id,
        payment_method_types=['card'],
        billing_address_collection='required',
        mode=mode,
        line_items=line_items
    )
    return checkout_session


@customer_id_required
def create_billing_portal_session(user: UserProtocol) -> stripe.billing_portal.Session:
    portal_session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
    )
    return portal_session


def create_stripe_subscription_checkout(user: UserProtocol, price_id: str) -> stripe.checkout.Session:
    checkout_session = create_checkout(user, "subscription", [
            {
                'price': price_id,
                'quantity': 1
            },
        ])
    return checkout_session


def list_subscriptions(user: UserProtocol, **kwargs):
    if user.stripe_customer_id:
        subscriptions = stripe.Subscription.list(customer=user.stripe_customer_id, **kwargs)
        return subscriptions['data']
    return []


def get_all_subscription_info(user: UserProtocol):
    data = list_subscriptions(user, status='all')
    return data


def list_active_subscriptions(user: UserProtocol):
    return list_subscriptions(user, status='active')


def check_subscription_product_id(sub: stripe.Subscription) -> str:
    return sub.get('plan', {}).get('product', None)


def check_subscription_price_id(sub: stripe.Subscription) -> str:
    return sub.get('plan', {}).get('id', None)


def list_products_subscribed_to(user: UserProtocol) -> List[Tuple[str, int]]:
    subscriptions = list_active_subscriptions(user)
    return [(check_subscription_product_id(sub), sub.get('cancel_at', None)) for sub in subscriptions]


def list_prices_subscribed_to(user: UserProtocol) -> List[str]:
    subscriptions = list_active_subscriptions(user)
    return [check_subscription_price_id(sub) for sub in subscriptions]


def is_subscribed_and_cancelled_time(user: UserProtocol, product_id: str) -> Dict[str, Any]:
    for sub in list_products_subscribed_to(user):
        if sub[0] == product_id:
            return {'subscribed': True, 'cancel_at': sub[1]}
    return {'subscribed': False, 'cancel_at': None}


def is_subscribed(user: UserProtocol, product_id: str) -> bool:
    return is_subscribed_and_cancelled_time(user, product_id)['subscribed']


def is_subscribed_with_cache(user: UserProtocol, product_id: str, cache: CacheProtocol) -> bool:
    cache_key = f'is_subscribed_{user.id}'
    subscribed = cache.get(cache_key)
    if subscribed is None:
        subscribed = is_subscribed(user, product_id)
        if subscribed:
            cache.set(cache_key, subscribed)
    return subscribed


@customer_id_required
def create_subscription(user: UserProtocol, price_id: str) -> stripe.Subscription:
    subscription = stripe.Subscription.create(
        customer=user.stripe_customer_id,
        items=[
            {"price": price_id},
        ],
    )
    return subscription


def cancel_subscription(user: UserProtocol, product_id: str) -> bool:
    sub_cancelled = False
    for sub in list_subscriptions(user):
        if check_subscription_product_id(sub) == product_id:
            sub_id = sub['id']
            stripe.Subscription.delete(sub_id)
            sub_cancelled = True
    return sub_cancelled


def _minimize_price(price: Dict[str, Any]) -> Dict[str, Any]:
    return {k: price[k] for k in ['id', 'recurring', 'type', 'unit_amount', 'unit_amount_decimal']}


def get_subscription_prices(user: UserProtocol, product_id: str) -> List[Dict[str, Any]]:
    response = stripe.Price.list(active=True, product=product_id)
    prices = [_minimize_price(p) for p in response['data']]
    if user:
        subscribed_prices = list_prices_subscribed_to(user)
    else:
        subscribed_prices = []
    for p in prices:
        p['subscribed'] = p['id'] in subscribed_prices
    return prices


@customer_id_required
def delete_customer(user: UserProtocol) -> Any:
    return stripe.Customer.delete(user.stripe_customer_id)
