import stripe
from concurrent.futures import ThreadPoolExecutor
from .decorators import customer_id_required
from .exceptions import StripeCustomerIdRequired, DefaultPaymentMethodRequired, StripeWrongCustomer
import itertools
from . import tests
from .types import (
    UserProtocol, CacheProtocol, PaymentMethodType, ProductSubscription, ProductIsSubscribed, Price, PriceSubscription,
    ProductPriceSubscription, Product, ProductDetail, PriceNoProductSubscriptionInfo
)
from .__version__ import version

from typing import Any, Dict, List, Optional, Generator, Union, Mapping

app_name = 'stripe-subscriptions'
app_url = "https://github.com/primal100/stripe-subscriptions"


stripe.set_app_info(app_name, version=version, url=app_url)


executor = ThreadPoolExecutor()


class User(UserProtocol):
    def __init__(self, user_id: Any, email: str, stripe_customer_id: Optional[str] = None):
        self.id = user_id
        self.email = email
        self.stripe_customer_id = stripe_customer_id


# Customer

def create_customer(user: UserProtocol, **kwargs) -> stripe.Customer:
    metadata = kwargs.pop('metadata', {})
    metadata['id'] = user.id
    customer = stripe.Customer.create(email=user.email, name=str(user), metadata=metadata, **kwargs)
    user.stripe_customer_id = customer['id']
    return customer


@customer_id_required
def delete_customer(user: UserProtocol) -> Any:
    response = stripe.Customer.delete(user.stripe_customer_id)
    user.stripe_customer_id = None
    return response


# Checkouts
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


def create_setup_checkout(user: UserProtocol, subscription_id: str = None, **kwargs) -> stripe.checkout.Session:
    if subscription_id:
        kwargs['setup_intent_data'] = kwargs.get('setup_intent_Data') or {}
        kwargs['setup_intent_data']["metadata"] = {**kwargs['setup_intent_data'].get('metadata', {}),
                                                   **{'subscription_id': subscription_id}}
    return create_checkout(user, "setup", **kwargs)


###Get Subscription Data###
def list_subscriptions(user: Optional[UserProtocol], **kwargs) -> List[stripe.Subscription]:
    if user and user.stripe_customer_id:
        subscriptions = stripe.Subscription.list(customer=user.stripe_customer_id, **kwargs)
        return subscriptions['data']
    return []


def list_active_subscriptions(user: Optional[UserProtocol], **kwargs) -> List[stripe.Subscription]:
    return list_subscriptions(user, status='active', **kwargs)


###Products & Prices###

def _check_subscription_product_id(sub: stripe.Subscription) -> str:
    return sub.get('plan', {}).get('product', None)


def _check_subscription_price_id(sub: stripe.Subscription) -> str:
    return sub.get('plan', {}).get('id', None)


def list_products_prices_subscribed_to(user: UserProtocol, **kwargs) -> List[ProductSubscription]:
    subscriptions = list_active_subscriptions(user, **kwargs)
    return [{'product_id': _check_subscription_product_id(sub),
             'price_id': _check_subscription_price_id(sub),
             'cancel_at': sub.get('cancel_at', None),
             'current_period_end': sub.get('current_period_end', None)
             } for sub in subscriptions]


def is_subscribed_and_cancelled_time(user: UserProtocol, product_id: Optional[str] = None,
                                     price_id: Optional[str] = None, **kwargs) -> ProductIsSubscribed:
    sub: ProductIsSubscribed
    for sub in list_products_prices_subscribed_to(user, **kwargs):
        if sub['product_id'] == product_id or sub['price_id'] == price_id:
            sub['subscribed'] = True
            return sub
    return {'subscribed': False, 'cancel_at': None, 'current_period_end': None, 'product_id': None, 'price_id': None}


def is_subscribed(user: UserProtocol, product_id: str = None, price_id: str = None) -> bool:
    return is_subscribed_and_cancelled_time(user, product_id, price_id)['subscribed']


def is_subscribed_with_cache(user: Optional[UserProtocol], cache: CacheProtocol,
                             product_id: Optional[str] = None, timeout: int = 3600) -> bool:
    """ Need to keep under 250 characters for memcached"""
    if not user or not user.stripe_customer_id:
        return False
    sanitized_userid = str(user.id)[-80:]
    cache_key = f'is_subscribed_{sanitized_userid}_{product_id}'
    subscribed = cache.get(cache_key)
    if subscribed is None:
        subscribed = is_subscribed(user, product_id)
        if subscribed:
            cache.set(cache_key, subscribed, timeout=timeout)
    return subscribed


def _minimize_price(price: Dict[str, Any]) -> Price:
    keys = ['id', 'recurring', 'type', 'currency', 'unit_amount', 'unit_amount_decimal', 'nickname',
            'product', 'metadata']
    return {k: price[k] for k in keys}


def get_active_prices(**kwargs) -> List[Price]:
    response = stripe.Price.list(active=True, **kwargs)
    return [_minimize_price(p) for p in response['data']]


def get_subscription_prices(user: Optional[UserProtocol] = None, **kwargs) -> List[PriceSubscription]:
    price_future = executor.submit(get_active_prices, **kwargs)
    subscribed_prices_future = executor.submit(list_products_prices_subscribed_to, user)
    prices = price_future.result()
    subscribed_prices = subscribed_prices_future.result()
    p: PriceSubscription
    for p in prices:
        p['subscription_info'] = {'subscribed': False, 'current_period_end': None, 'cancel_at': None}
        for s in subscribed_prices:
            if s['price_id'] == p['id']:
                p['subscription_info'] = {'subscribed': True, 'cancel_at': s['cancel_at'],
                                          'current_period_end': s['current_period_end']}
    return prices


def retrieve_price(user: Optional[UserProtocol], price_id: str) -> PriceSubscription:
    price_future = executor.submit(stripe.Price.retrieve, price_id)
    subscription_info = is_subscribed_and_cancelled_time(user, price_id=price_id)
    price = _minimize_price(price_future.result())
    price["subscription_info"] = {
        'subscribed': subscription_info['subscribed'],
        'current_period_end': subscription_info['current_period_end'],
        'cancel_at': subscription_info['cancel_at']
    }
    return price


def _minimize_product(product: stripe.Product) -> Product:
    keys = ['id', 'images', 'type', 'name', 'shippable', 'unit_label', 'url', 'metadata']
    return {k: product[k] for k in keys}


def get_active_products(**kwargs) -> List[Product]:
    response = stripe.Product.list(active=True, **kwargs)
    return [_minimize_product(product) for product in response]


def get_subscription_products_and_prices(user: Optional[UserProtocol] = None,
                                         price_kwargs: Optional[Dict[str, Any]] = None,
                                         **kwargs) -> List[ProductDetail]:
    products_future = executor.submit(get_active_products, **kwargs)
    price_kwargs = price_kwargs or {}
    prices = get_subscription_prices(user, **price_kwargs)
    product: ProductDetail
    products = products_future.result()
    for product in products:
        product['prices'] = []
        product['subscription_info'] = {'subscribed': False, 'current_period_end': None, 'cancel_at': None}
    price: PriceNoProductSubscriptionInfo
    for price in prices:
        product_id = price.pop('product', None)
        if product_id:
            for product in products:
                if product_id == product['id']:
                    product['prices'].append(price)
                    if price['subscription_info']['subscribed']:
                        product['subscription_info'] = price['subscription_info']
    return products


def retrieve_product(user: Optional[UserProtocol], product_id: str,
                     price_kwargs: Optional[Dict[str, Any]] = None) -> ProductDetail:
    product_future = executor.submit(stripe.Product.retrieve, product_id)
    price_kwargs = price_kwargs or {}
    prices = get_subscription_prices(user, product=product_id, **price_kwargs)
    product: ProductDetail = _minimize_product(product_future.result())
    product['prices'] = prices
    product['subscription_info'] = {'subscribed': False, 'current_period_end': None, 'cancel_at': None}
    price: PriceNoProductSubscriptionInfo
    for price in prices:
        price.pop('product')
        if price['subscription_info']['subscribed']:
            product['subscription_info'] = price['subscription_info']
    return product


# Setup Intents
@customer_id_required
def create_setup_intent(user: UserProtocol, payment_method_types: List[PaymentMethodType] = None,
                        **kwargs) -> stripe.SetupIntent:
    setup_intent_kwargs = {
        'customer': user.stripe_customer_id,
        'confirm': False,
        'payment_method_types': payment_method_types,
        'usage': "off_session"}
    setup_intent_kwargs.update(kwargs)
    return stripe.SetupIntent.create(**setup_intent_kwargs)


# Payment Methods
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


def _check_default_payment_method_kwargs(set_as_default_payment_method: bool,
                                         default_payment_method: Optional[str] = None, **kwargs) -> bool:
    if set_as_default_payment_method and not default_payment_method:
        raise DefaultPaymentMethodRequired
    return set_as_default_payment_method


# Subscriptions
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


# Generic Methods For Existing Objects
@customer_id_required
def allow_if_owned_by_user(user: Optional[UserProtocol], obj_class,
                           obj_id: str, action: str) -> Mapping[str, Any]:
    obj = obj_class.retrieve(obj_id)
    if not user or obj['customer'] != user.stripe_customer_id:
        msg = f"Customer {user.stripe_customer_id} cannot {action} {obj['object']} {obj_id} as they do not own it."
        raise StripeWrongCustomer(msg)
    return obj


def retrieve(user: UserProtocol, obj_cls, obj_id: str, action="retrieve") -> Mapping[str, Any]:
    obj = allow_if_owned_by_user(user, obj_cls, obj_id, action)
    return obj


def delete(user: UserProtocol, obj_cls, obj_id: str, action: str = "delete"):
    obj = retrieve(user, obj_cls, obj_id, action=action)
    return obj_cls.delete(obj)


def modify(user: UserProtocol, obj_cls, obj_id: str, action: str = "modify",
           **kwargs) -> Union[Mapping[str, Any], stripe.Subscription]:
    obj = retrieve(user, obj_cls, obj_id, action=action)
    return obj_cls.modify(obj["id"], **kwargs)


# Change Existing Payment Methods
def detach_all_payment_methods(user: Optional[UserProtocol], types: List[PaymentMethodType],
                               **kwargs) -> List[stripe.PaymentMethod]:
    if user and user.stripe_customer_id:
        futures = [executor.submit(stripe.PaymentMethod.detach,
                                   payment_type)
                   for payment_type in list_payment_methods(user, types, **kwargs)]
        return [f.result() for f in futures]
    return []


def detach_payment_method(user: Optional[UserProtocol], payment_method_id: str) -> stripe.PaymentMethod:
    obj = retrieve(user, stripe.PaymentMethod, payment_method_id, action="detach")
    return stripe.PaymentMethod.detach(obj["id"])


# Change Existing Subscriptions
def cancel_subscription(user: UserProtocol, subscription_id: str) -> stripe.Subscription:
    return delete(user, stripe.Subscription, subscription_id)


def cancel_subscription_for_product(user: UserProtocol, product_id: str) -> bool:
    sub_cancelled = False
    for sub in list_subscriptions(user):
        if _check_subscription_product_id(sub) == product_id:
            sub_id = sub['id']
            stripe.Subscription.delete(sub_id)
            sub_cancelled = True
    return sub_cancelled


@customer_id_required
def update_default_payment_method_all_subscriptions(user: UserProtocol, default_payment_method: str) -> stripe.Customer:
    customer_fut = executor.submit(stripe.Customer.modify, user.stripe_customer_id, invoice_settings={
        'default_payment_method': default_payment_method})
    subs = list_subscriptions(user)
    fs = [executor.submit(stripe.Subscription.modify, sub["id"], default_payment_method=default_payment_method)
          for sub in subs if sub['default_payment_method'] != default_payment_method]
    [f.result() for f in fs]
    return customer_fut.result()


def modify_subscription(user: UserProtocol, subscription_id: str,
                        set_as_default_payment_method: bool = False, **kwargs) -> stripe.Subscription:
    _check_default_payment_method_kwargs(set_as_default_payment_method, **kwargs)
    sub = modify(user, stripe.Subscription, subscription_id, **kwargs)
    if set_as_default_payment_method:
        update_default_payment_method_all_subscriptions(user, **kwargs)
    return sub
