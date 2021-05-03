import stripe
from concurrent.futures import ThreadPoolExecutor
from .decorators import customer_id_required
from .exceptions import StripeCustomerIdRequired, SubscriptionArgsMissingException
from . import tests
from .types import UserProtocol, CacheProtocol
from .__version__ import version

from typing import Any, Dict, List, Optional


app_name = 'stripe-subscriptions'
app_url = "https://github.com/primal100/stripe-subscriptions"


stripe.set_app_info(app_name, version=version, url=app_url)


executor = ThreadPoolExecutor()


class User(UserProtocol):
    def __init__(self, user_id: Any, email: str, stripe_customer_id: Optional[str] = None):
        self.id = user_id
        self.email = email
        self.stripe_customer_id = stripe_customer_id


def create_customer(user: UserProtocol, **kwargs) -> stripe.Customer:
    metadata = kwargs.pop('metadata', {})
    metadata ['id'] = user.id
    customer = stripe.Customer.create(email=user.email, name=str(user), metadata=metadata, **kwargs)
    user.stripe_customer_id = customer['id']
    return customer


@customer_id_required
def delete_customer(user: UserProtocol) -> Any:
    response = stripe.Customer.delete(user.stripe_customer_id)
    user.stripe_customer_id = None
    return response


@customer_id_required
def create_checkout(user: UserProtocol, mode: str, line_items: List[Dict[str, Any]],
                    **kwargs) -> stripe.checkout.Session:
    return stripe.checkout.Session.create(
        client_reference_id=user.id,
        customer=user.stripe_customer_id,
        mode=mode,
        line_items=line_items,
        **kwargs
    )


def create_subscription_checkout(user: UserProtocol, price_id: str, **kwargs) -> stripe.checkout.Session:
    return create_checkout(user, "subscription", [
            {
                'price': price_id,
                'quantity': 1
            },
        ], **kwargs)


def list_subscriptions(user: UserProtocol, **kwargs) -> List[stripe.Subscription]:
    if user.stripe_customer_id:
        subscriptions = stripe.Subscription.list(customer=user.stripe_customer_id, **kwargs)
        return subscriptions['data']
    return []


def get_all_subscription_info(user: UserProtocol, **kwargs) -> List[stripe.Subscription]:
    return list_subscriptions(user, status='all', **kwargs)


def list_active_subscriptions(user: UserProtocol, **kwargs) -> List[stripe.Subscription]:
    return list_subscriptions(user, status='active', **kwargs)


def _check_subscription_product_id(sub: stripe.Subscription) -> str:
    return sub.get('plan', {}).get('product', None)


def _check_subscription_price_id(sub: stripe.Subscription) -> str:
    return sub.get('plan', {}).get('id', None)


def _check_subscription_cancel_at(sub: stripe.Subscription) -> Optional[int]:
    return sub.get('cancel_at', None)


def list_products_subscribed_to(user: UserProtocol, **kwargs) -> List[Dict[str, Any]]:
    subscriptions = list_active_subscriptions(user, **kwargs)
    return [{'product_id': _check_subscription_product_id(sub),
             'cancel_at': _check_subscription_cancel_at(sub)} for sub in subscriptions]


def list_prices_subscribed_to(user: UserProtocol, **kwargs) -> List[Dict[str, Any]]:
    subscriptions = list_active_subscriptions(user, limit=100, **kwargs)
    return [{'price_id': _check_subscription_price_id(sub),
             'cancel_at': _check_subscription_cancel_at(sub)} for sub in subscriptions]


def is_subscribed_and_cancelled_time(user: UserProtocol, product_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    for sub in list_active_subscriptions(user, **kwargs):
        if _check_subscription_product_id(sub) == product_id:
            return {'subscribed': True, 'cancel_at': _check_subscription_cancel_at(sub)}
    return {'subscribed': False, 'cancel_at': None}


def is_subscribed(user: UserProtocol, product_id: str = None) -> bool:
    return is_subscribed_and_cancelled_time(user, product_id)['subscribed']


def is_subscribed_with_cache(user: UserProtocol, cache: CacheProtocol,
                             product_id: Optional[str] = None) -> bool:
    """ Need to keep under 250 characters for memcached"""
    sanitized_userid = str(user.id)[-80:]
    cache_key = f'is_subscribed_{product_id}_{sanitized_userid}'
    subscribed = cache.get(cache_key)
    if subscribed is None:
        subscribed = is_subscribed(user, product_id)
        if subscribed:
            cache.set(cache_key, subscribed)
    return subscribed


@customer_id_required
def create_subscription(user: UserProtocol, price_id: str, **kwargs) -> stripe.Subscription:
    return stripe.Subscription.create(
        customer=user.stripe_customer_id,
        items=[
            {"price": price_id},
        ],
        **kwargs
    )


def cancel_subscription(user: UserProtocol, product_id: str) -> bool:
    sub_cancelled = False
    for sub in list_subscriptions(user):
        if _check_subscription_product_id(sub) == product_id:
            sub_id = sub['id']
            stripe.Subscription.delete(sub_id)
            sub_cancelled = True
    return sub_cancelled


def _minimize_price(price: Dict[str, Any], include_product_id: bool = True) -> Dict[str, Any]:
    keys = ['id', 'recurring', 'type', 'currency', 'unit_amount', 'unit_amount_decimal', 'nickname', 'metadata']
    if include_product_id:
        keys.append('product')
    return {k: price[k] for k in keys}


def get_active_prices(include_product_id: bool = True, **kwargs) -> List[Dict[str, Any]]:
    response = stripe.Price.list(active=True, **kwargs)
    return [_minimize_price(p, include_product_id=include_product_id) for p in response['data']]


def get_subscription_prices(user: Optional[UserProtocol] = None, **kwargs) -> List[Dict[str, Any]]:
    price_future = executor.submit(get_active_prices, **kwargs)
    subscribed_prices_future = executor.submit(list_prices_subscribed_to, user)
    prices = price_future.result()
    subscribed_prices = subscribed_prices_future.result()
    for p in prices:
        p['subscription_info'] = {'subscribed': False, 'cancel_at': None}
        for s in subscribed_prices:
            if s['price_id'] == p['id']:
                p['subscription_info'] = {'subscribed': True, 'cancel_at': s['cancel_at']}
    return prices


def _minimize_product(product: Dict[str, Any]) -> Dict[str, Any]:
    keys = ['id', 'images', 'type', 'name', 'shippable', 'type', 'unit_label', 'url', 'metadata']
    return {k: product[k] for k in keys}


def get_active_products(**kwargs) -> List[Dict[str, Any]]:
    response = stripe.Product.list(active=True, **kwargs)
    return [_minimize_product(product) for product in response]


def get_subscription_products_and_prices(user: Optional[UserProtocol] = None,
                                         price_kwargs: Optional[Dict[str, Any]] = None,
                                         **kwargs) -> List[Dict[str, Any]]:
    products_future = executor.submit(get_active_products, **kwargs)
    price_kwargs = price_kwargs or {}
    prices = get_subscription_prices(user, **price_kwargs)
    products = products_future.result()
    for product in products:
        product['prices'] = []
        product['subscription_info'] = {'subscribed': False, 'cancel_at': None}
    for price in prices:
        product_id = price.pop('product', None)
        if product_id:
            for product in products:
                if product_id == product['id']:
                    product['prices'].append(price)
                    if price['subscription_info']['subscribed']:
                        product['subscription_info'] = price['subscription_info']
    return products
