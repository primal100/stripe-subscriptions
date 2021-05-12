import stripe
from concurrent.futures import ThreadPoolExecutor
from .decorators import customer_id_required, check_if_user_can_update
from .exceptions import StripeCustomerIdRequired, DefaultPaymentMethodRequired
import itertools
from . import tests
from .types import UserProtocol, CacheProtocol, PaymentMethodType
from .__version__ import version

from typing import Any, Dict, List, Optional, Generator


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
def create_checkout(user: UserProtocol, mode: str, line_items: List[Dict[str, Any]] = None,
                    **kwargs) -> stripe.checkout.Session:
    return stripe.checkout.Session.create(
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


def create_setup_checkout(user: UserProtocol, **kwargs) -> stripe.checkout.Session:
    return create_checkout(user, "setup", **kwargs)


def list_subscriptions(user: Optional[UserProtocol], **kwargs) -> List[stripe.Subscription]:
    if user and user.stripe_customer_id:
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


def is_subscribed_with_cache(user: Optional[UserProtocol], cache: CacheProtocol,
                             product_id: Optional[str] = None) -> bool:
    """ Need to keep under 250 characters for memcached"""
    if not user or not user.stripe_customer_id:
        return False
    sanitized_userid = str(user.id)[-80:]
    cache_key = f'is_subscribed_{product_id}_{sanitized_userid}'
    subscribed = cache.get(cache_key)
    if subscribed is None:
        subscribed = is_subscribed(user, product_id)
        if subscribed:
            cache.set(cache_key, subscribed)
    return subscribed


@customer_id_required
def update_default_payment_method_all_subscriptions(user: UserProtocol, default_payment_method: str) -> stripe.Customer:
    customer_fut = executor.submit(stripe.Customer.modify, user.stripe_customer_id, invoice_settings={
        'default_payment_method': default_payment_method})
    subs = list_subscriptions(user)
    fs = [executor.submit(stripe.Subscription.modify, sub["id"], default_payment_method=default_payment_method)
          for sub in subs if sub['default_payment_method'] != default_payment_method]
    [f.result() for f in fs]
    return customer_fut.result()


def _check_default_payment_method_kwargs(set_as_default_payment_method: bool,
                                         default_payment_method: Optional[str] = None, **kwargs):
    if set_as_default_payment_method and not default_payment_method:
        raise DefaultPaymentMethodRequired
    return set_as_default_payment_method


@customer_id_required
def create_subscription(user: UserProtocol, price_id: str,
                        set_as_default_payment_method: bool = False, **kwargs) -> stripe.Subscription:
    _check_default_payment_method_kwargs(set_as_default_payment_method, **kwargs)
    sub = stripe.Subscription.create(
        customer=user.stripe_customer_id,
        items=[
            {"price": price_id},
        ],
        **kwargs
    )
    if set_as_default_payment_method:
        update_default_payment_method_all_subscriptions(user, **kwargs)
    return sub


def cancel_subscription_for_product(user: UserProtocol, product_id: str) -> bool:
    sub_cancelled = False
    for sub in list_subscriptions(user):
        if _check_subscription_product_id(sub) == product_id:
            sub_id = sub['id']
            stripe.Subscription.delete(sub_id)
            sub_cancelled = True
    return sub_cancelled


@check_if_user_can_update(stripe.Subscription, action="cancel")
def cancel_subscription(user: UserProtocol, sub: stripe.Subscription) -> stripe.Subscription:
    return stripe.Subscription.delete(sub)


@check_if_user_can_update(stripe.Subscription, action="modify")
def modify_subscription(user: UserProtocol, sub: stripe.Subscription, **kwargs) -> stripe.Subscription:
    return stripe.Subscription.modify(sub["id"], **kwargs)


def _minimize_price(price: Dict[str, Any]) -> Dict[str, Any]:
    keys = ['id', 'recurring', 'type', 'currency', 'unit_amount', 'unit_amount_decimal', 'nickname',
            'product', 'metadata']
    return {k: price[k] for k in keys}


def get_active_prices(**kwargs) -> List[Dict[str, Any]]:
    response = stripe.Price.list(active=True, **kwargs)
    return [_minimize_price(p) for p in response['data']]


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


@customer_id_required
def create_setup_intent(user, payment_method_types: List[PaymentMethodType] = None, **kwargs) -> stripe.SetupIntent:
    setup_intent_kwargs = {
        'customer': user.stripe_customer_id,
        'confirm': False,
        'payment_method_types': payment_method_types,
        'usage': "off_session"}
    setup_intent_kwargs.update(kwargs)
    return stripe.SetupIntent.create(**setup_intent_kwargs)


def list_payment_methods(user: Optional[UserProtocol], types: List[PaymentMethodType],
                         **kwargs) -> Generator[stripe.PaymentMethod, None, None]:
    """
    Stripe only allows to retrieve payment methods for a single type at a time.
    This functions gathers payment methods from multiple types
    """
    if not user or not user.stripe_customer_id or len(types) == 0:
        yield from []
    else:
        customer_future = executor.submit(stripe.Customer.retrieve, user.stripe_customer_id)
        futures = [executor.submit(stripe.PaymentMethod.list,
                                   customer=user.stripe_customer_id, type=payment_type, **kwargs)
                   for payment_type in types]
        customer = customer_future.result()
        default_payment_method = customer['invoice_settings']['default_payment_method']
        for payment_method in itertools.chain(*[f.result() for f in futures]):
            payment_method['default'] = payment_method['id'] == default_payment_method
            yield payment_method


@check_if_user_can_update(stripe.PaymentMethod, action="detach")
def detach_payment_method(user: Optional[UserProtocol], payment_method: stripe.PaymentMethod) -> stripe.PaymentMethod:
    return stripe.PaymentMethod.detach(payment_method)


def detach_all_payment_methods(user: Optional[UserProtocol], types: List[PaymentMethodType],
                               **kwargs) -> List[stripe.PaymentMethod]:
    if user and user.stripe_customer_id:
        futures = [executor.submit(stripe.PaymentMethod.detach,
                                   payment_type)
                   for payment_type in list_payment_methods(user, types, **kwargs)]
        return [f.result() for f in futures]
    return []
