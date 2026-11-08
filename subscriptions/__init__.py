import stripe
from concurrent.futures import ThreadPoolExecutor
from .decorators import customer_id_required
from .exceptions import StripeCustomerIdRequired, DefaultPaymentMethodRequired, StripeWrongCustomer
import itertools
from . import tests
from .types import (
    UserProtocol, PaymentMethodType, ProductSubscription, ProductIsSubscribed, Price, PriceSubscription,
    Product, ProductDetail, PriceNoProductSubscriptionInfo,
    RetrievableResource, ModifiableResource, DeletableResource
)
from .__version__ import version

from typing import Any, Dict, List, Optional, Generator, Union, Mapping, TypeVar, Literal, cast

ResourceT = TypeVar('ResourceT', bound=stripe.StripeObject)
ResourceData = Union[stripe.StripeObject, Mapping[str, Any]]

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
    """
    Creates a new customer over the stripe API using the user data. The customer id is set on the user object but not saved.
    The customer id must be saved to the database after this function is called. e.g. by calling user.save().
    """
    metadata = kwargs.pop('metadata', {})
    metadata['id'] = user.id
    customer = stripe.Customer.create(email=user.email, name=str(user), metadata=metadata, **kwargs)
    user.stripe_customer_id = customer['id']
    return customer


@customer_id_required
def delete_customer(user: UserProtocol) -> stripe.Customer:
    """
    Deletes a customer from Stripe. Sets the customer id on the user object to none but this is not saved.
    The customer id must be saved to the database after this function is called, e.g. by calling user.save().
    An exception will be raised if the user does already not have a customer id set.
    """
    response = stripe.Customer.delete(cast(str, user.stripe_customer_id))
    user.stripe_customer_id = None
    return response


# Checkouts
@customer_id_required
def create_checkout(user: UserProtocol, mode: Literal["payment", "setup", "subscription"],
                    line_items: Optional[List[Dict[str, Any]]] = None,
                    **kwargs) -> stripe.checkout.Session:
    """
    Creates a new Stripe checkout session for this user.
    Returns the full Session; use its id and url for a hosted Checkout response.
    Recommended to call create_subscription_checkout or create_setup_checkout instead.
    An exception will be raised if the user does already not have a customer id set.
    """
    params: Dict[str, Any] = dict(kwargs)
    if line_items is not None:
        params['line_items'] = line_items
    return stripe.checkout.Session.create(
        customer=cast(str, user.stripe_customer_id), mode=mode, **params
    )


def create_subscription_checkout(user: UserProtocol, price_id: str, **kwargs) -> stripe.checkout.Session:
    """
    Creates a new Stripe subscription checkout session for this user for the given price.
    Returns the full Session, including its hosted Checkout url and id.
    An exception will be raised if the user does already not have a customer id set.
    """
    return create_checkout(user, "subscription", [
            {
                'price': price_id,
                'quantity': 1
            },
        ], **kwargs)


def create_setup_checkout(user: UserProtocol, subscription_id: Optional[str] = None, **kwargs) -> stripe.checkout.Session:
    """
    Creates a new Stripe setup checkout session for this user, allowing them to add a new payment method for future use.
    Returns the full Session, including its hosted Checkout url and id.
    An exception will be raised if the user does already not have a customer id set.
    """
    if subscription_id:
        kwargs['setup_intent_data'] = kwargs.get('setup_intent_Data') or {}
        kwargs['setup_intent_data']["metadata"] = {**kwargs['setup_intent_data'].get('metadata', {}),
                                                   **{'subscription_id': subscription_id}}
    return create_checkout(user, "setup", **kwargs)


# Generic Methods For Accessing Existing Objects
@customer_id_required
def allow_if_owned_by_user(user: Optional[UserProtocol], obj_class: RetrievableResource[ResourceT],
                           obj_id: str, action: str) -> ResourceT:
    """
    Allow access to an object for viewing, modifying and deleting only if a user owns it.
    If user tries to access an object belonging to another user, StripeWrongCustomer exception is raised.
    The action word is included in the exception.
    """
    obj = obj_class.retrieve(obj_id)
    if user is None:
        raise StripeCustomerIdRequired
    if obj['customer'] != user.stripe_customer_id:
        msg = f"Customer {user.stripe_customer_id} cannot {action} {obj['object']} {obj_id} as they do not own it."
        raise StripeWrongCustomer(msg)
    return obj


def retrieve(user: Optional[UserProtocol], obj_cls: RetrievableResource[ResourceT], obj_id: str,
             action: str = "retrieve") -> ResourceT:
    """
    Retrieve an object over Stripe API for the given obj_id and obj_cls.
    obj_cls could be stripe.Subscription, stripe.PaymentMethod, stripe.Invoice, etc.
    If a customer attempts to retrieve an object belonging to another customer, StripeWrongCustomer exception is raised.
    The action word if provided is included in StripeWrongCustomer exception if raised.
    """
    return allow_if_owned_by_user(user, obj_cls, obj_id, action)


def delete(user: UserProtocol, obj_cls: DeletableResource[ResourceT], obj_id: str,
           action: str = "delete") -> ResourceT:
    """
    Delete an object over Stripe API with given obj_id for obj_cls.
    obj_cls could be stripe.Subscription, stripe.PaymentMethod, stripe.Invoice, etc.
    It is needed to retrieve the obj first to check the customer id.
    If a customer attempts to delete an object belonging to another customer, StripeWrongCustomer exception is raised.
    The action word if provided is included in StripeWrongCustomer exception if raised.
    """
    obj = retrieve(user, obj_cls, obj_id, action=action)
    return obj_cls.delete(obj["id"])


def modify(user: UserProtocol, obj_cls: ModifiableResource[ResourceT], obj_id: str, action: str = "modify",
           **kwargs: Any) -> ResourceT:
    """
    Modify an object over Stripe API with given obj_id for obj_cls.
    obj_cls could be stripe.Subscription, stripe.PaymentMethod, stripe.Invoice, etc.
    It is needed to retrieve the obj first to check the customer id.
    If a customer attempts to modify an object belonging to another customer, StripeWrongCustomer exception is raised.
    kwargs are the parameters to be modified.
    The action word if provided is included in StripeWrongCustomer exception if raised.
    """
    obj = retrieve(user, obj_cls, obj_id, action=action)
    return obj_cls.modify(obj["id"], **kwargs)


# Manage Subscriptions

def list_subscriptions(user: Optional[UserProtocol], **kwargs) -> List[stripe.Subscription]:
    """
    List all subscriptions for a user. Filters can be applied with kwargs according to the Stripe API.
    """
    if user and user.stripe_customer_id:
        subscriptions = stripe.Subscription.list(customer=user.stripe_customer_id, **kwargs)
        return subscriptions.data
    return []


def list_active_subscriptions(user: Optional[UserProtocol], **kwargs) -> List[stripe.Subscription]:
    """
    List all active subscriptions for a user.
    """
    return list_subscriptions(user, status='active', **kwargs)


def cancel_subscription(user: UserProtocol, subscription_id: str) -> stripe.Subscription:
    """
    Allow a user to cancel their subscription by subscription_id.
    If a user attempts to cancel a subscription belonging to another customer, StripeWrongCustomer will be raised.
    """
    sub = retrieve(user, stripe.Subscription, subscription_id, action="cancel")
    return stripe.Subscription.cancel(sub["id"])


def cancel_subscription_for_product(user: UserProtocol, product_id: str) -> bool:
    """
    Allow a user to cancel their subscription by the id of the product they are subscribed to, if such a subscription exists.
    Returns True if the subscription exists for that user, otherwise False.
    """
    sub_cancelled = False
    for sub in list_subscriptions(user):
        if _check_subscription_product_id(sub) == product_id:
            sub_id = sub['id']
            stripe.Subscription.cancel(sub_id)
            sub_cancelled = True
    return sub_cancelled


@customer_id_required
def update_default_payment_method_all_subscriptions(user: UserProtocol, default_payment_method: str) -> stripe.Customer:
    """
    Change the default payment method for the user and for all subscriptions belonging to that user.
    """
    customer_fut = executor.submit(stripe.Customer.modify, cast(str, user.stripe_customer_id), invoice_settings={
        'default_payment_method': default_payment_method})
    subs = list_subscriptions(user)
    fs = [executor.submit(stripe.Subscription.modify, sub["id"], default_payment_method=default_payment_method)
          for sub in subs if sub['default_payment_method'] != default_payment_method]
    [f.result() for f in fs]
    return customer_fut.result()


def modify_subscription(user: UserProtocol, subscription_id: str,
                        set_as_default_payment_method: bool = False, **kwargs) -> stripe.Subscription:
    """
    Modify a user's subscription
    kwargs is the parameters to modify.
    If payment_method is given in kwargs and set_as_default_payment_method is true, the default payment method is changed to that payment method for all subscriptions.
    Raises StripeWrongCustomer is a user tries to modify a subscription belonging to another customer.
    """
    _check_default_payment_method_kwargs(set_as_default_payment_method, **kwargs)
    sub = modify(user, stripe.Subscription, subscription_id, **kwargs)
    if set_as_default_payment_method:
        update_default_payment_method_all_subscriptions(user, **kwargs)
    return sub


def _check_default_payment_method_kwargs(set_as_default_payment_method: bool,
                                         default_payment_method: Optional[str] = None, **kwargs) -> bool:
    """
    Helper function to check if kwargs have been provided to update a customer's default payment method.
    """
    if set_as_default_payment_method and not default_payment_method:
        raise DefaultPaymentMethodRequired
    return set_as_default_payment_method


@customer_id_required
def create_subscription(user: UserProtocol, price_id: str,
                        set_as_default_payment_method: bool = False, **kwargs) -> stripe.Subscription:
    """
    Create a new subscription. A payment method must already be created.
    If set_as_default_payment_method is true, the given payment method will be set as the default for this customer.
    kwargs is a list of parameters to provide to stripe.Subscription.create in the Stripe API.
    """
    _check_default_payment_method_kwargs(set_as_default_payment_method, **kwargs)
    sub = stripe.Subscription.create(
        customer=cast(str, user.stripe_customer_id),
        items=[
            {"price": price_id},
        ],
        **kwargs
    )
    if set_as_default_payment_method:
        update_default_payment_method_all_subscriptions(user, **kwargs)
    return sub


# Products & Prices


def _resource_dict(resource: ResourceData) -> Mapping[str, Any]:
    """Convert SDK resources to JSON-compatible dictionaries recursively."""
    return resource.to_dict(for_json=True) if isinstance(resource, stripe.StripeObject) else resource


def _check_subscription_product_id(sub: ResourceData) -> Optional[str]:
    """
    Easy way to get the product_id a subscription is for
    """
    return (_resource_dict(sub).get('plan') or {}).get('product')


def _check_subscription_price_id(sub: ResourceData) -> Optional[str]:
    """
    Easy way to get the price_id a subscription is for
    """
    return (_resource_dict(sub).get('plan') or {}).get('id')


def list_products_prices_subscribed_to(user: Optional[UserProtocol], **kwargs) -> List[ProductSubscription]:
    """
    Flat data for each active subscription item, including its own billing period.
    """
    result: List[ProductSubscription] = []
    for resource in list_active_subscriptions(user, **kwargs):
        sub = _resource_dict(resource)
        items = (sub.get('items') or {}).get('data', [])
        if items:
            for item in items:
                price = item.get('price') or item.get('plan') or {}
                product = price.get('product')
                result.append({
                    'sub_id': sub['id'],
                    'product_id': product.get('id') if isinstance(product, dict) else product,
                    'price_id': price.get('id'),
                    'cancel_at': sub.get('cancel_at'),
                    'current_period_end': item.get('current_period_end', sub.get('current_period_end')),
                })
        else:
            # Older API responses can expose only the subscription-level plan and period.
            result.append({
                'sub_id': sub['id'],
                'product_id': _check_subscription_product_id(sub),
                'price_id': _check_subscription_price_id(sub),
                'cancel_at': sub.get('cancel_at'),
                'current_period_end': sub.get('current_period_end'),
            })
    return result


def is_subscribed_and_cancelled_time(user: Optional[UserProtocol], product_id: Optional[str] = None,
                                     price_id: Optional[str] = None, **kwargs) -> ProductIsSubscribed:
    """
    Return first active subscription for a specific product or price or none to quickly check if a user is subscribed.
    """
    for sub in list_products_prices_subscribed_to(user, **kwargs):
        if sub['product_id'] == product_id or sub['price_id'] == price_id:
            return {
                'sub_id': sub['sub_id'], 'product_id': sub['product_id'],
                'price_id': sub['price_id'], 'cancel_at': sub['cancel_at'],
                'current_period_end': sub['current_period_end'],
            }
    return {'sub_id': None, 'cancel_at': None, 'current_period_end': None, 'product_id': None, 'price_id': None}


def is_subscribed(user: Optional[UserProtocol], product_id: Optional[str] = None,
                  price_id: Optional[str] = None) -> bool:
    """
    Returns a simple true or false to check if a user subscribed to the given product or price.
    """
    return bool(is_subscribed_and_cancelled_time(user, product_id, price_id)['sub_id'])


def _minimize_price(price: ResourceData) -> Price:
    """
    Return only the keys and values of a price the end user would be interested in.
    """
    price = _resource_dict(price)
    return {
        'id': price['id'], 'recurring': price['recurring'], 'type': price['type'],
        'currency': price['currency'], 'unit_amount': price['unit_amount'],
        'unit_amount_decimal': price['unit_amount_decimal'], 'nickname': price['nickname'],
        'product': price['product'], 'metadata': price['metadata'],
    }


def get_active_prices(**kwargs) -> List[Price]:
    """
    List all active prices
    kwargs is a list of filters to provide to stripe.Price.list as in the Stripe API.
    """
    response = stripe.Price.list(active=True, **kwargs)
    return [_minimize_price(p) for p in response.data]


def get_subscription_prices(user: Optional[UserProtocol] = None, **kwargs) -> List[PriceSubscription]:
    """
    Makes multiple requests to Stripe API to return the list of active prices with subscription data for each one for the given user.
    kwargs is a list of filters to provide to stripe.Price.list as in the Stripe API.
    """
    price_future = executor.submit(get_active_prices, **kwargs)
    subscribed_prices_future = executor.submit(list_products_prices_subscribed_to, user)
    prices = price_future.result()
    subscribed_prices = subscribed_prices_future.result()
    result: List[PriceSubscription] = []
    for price in prices:
        p: PriceSubscription = {**price, 'subscription_info': {
            'sub_id': None, 'current_period_end': None, 'cancel_at': None,
        }}
        for s in subscribed_prices:
            if s['price_id'] == p['id']:
                p['subscription_info'] = {'sub_id': s['sub_id'], 'cancel_at': s['cancel_at'],
                                          'current_period_end': s['current_period_end']}
        result.append(p)
    return result


def retrieve_price(user: Optional[UserProtocol], price_id: str) -> PriceSubscription:
    """
    Retrieve a single price with subscription info
    """
    price_future = executor.submit(stripe.Price.retrieve, price_id)
    subscription_info = is_subscribed_and_cancelled_time(user, price_id=price_id)
    price = _minimize_price(price_future.result())
    return {**price, "subscription_info": {
        'sub_id': subscription_info['sub_id'],
        'current_period_end': subscription_info['current_period_end'],
        'cancel_at': subscription_info['cancel_at']
    }}


def _minimize_product(product: ResourceData) -> Product:
    """
    Return only the keys and values of a product the end user would be interested in.
    """
    product = _resource_dict(product)
    return {
        'id': product['id'], 'images': product['images'], 'type': product['type'],
        'name': product['name'], 'shippable': product['shippable'],
        'unit_label': product['unit_label'], 'url': product['url'], 'metadata': product['metadata'],
    }


def get_active_products(**kwargs) -> List[Product]:
    """
    Get a list of active products with the most important keys for the end user to see.
    kwargs is a list of filters to provide to stripe.Product.list as in Stripe API.
    """
    response = stripe.Product.list(active=True, **kwargs)
    return [_minimize_product(product) for product in response]


def get_subscription_products_and_prices(user: Optional[UserProtocol] = None,
                                         price_kwargs: Optional[Dict[str, Any]] = None,
                                         **kwargs) -> List[ProductDetail]:
    """
    Get a list of active products with their prices and subscription information included in the result.
    kwargs is a list of filters product to stripe.Product.list.
    price_kwargs is a list of filters provided to stripe.Price.list
    """
    products_future = executor.submit(get_active_products, **kwargs)
    price_kwargs = price_kwargs or {}
    prices = get_subscription_prices(user, **price_kwargs)
    products: List[ProductDetail] = [
        {**product, 'prices': [], 'subscription_info': {
            'sub_id': None, 'current_period_end': None, 'cancel_at': None,
        }} for product in products_future.result()
    ]
    for price in prices:
        for product in products:
            if price['product'] == product['id']:
                product['prices'].append(_price_without_product(price))
                if price['subscription_info']['sub_id']:
                    product['subscription_info'] = price['subscription_info']
    return products


def _price_without_product(price: PriceSubscription) -> PriceNoProductSubscriptionInfo:
    return {
        'id': price['id'], 'recurring': price['recurring'], 'type': price['type'],
        'currency': price['currency'], 'unit_amount': price['unit_amount'],
        'unit_amount_decimal': price['unit_amount_decimal'], 'nickname': price['nickname'],
        'metadata': price['metadata'], 'subscription_info': price['subscription_info'],
    }


def retrieve_product(user: Optional[UserProtocol], product_id: str,
                     price_kwargs: Optional[Dict[str, Any]] = None) -> ProductDetail:
    """
    Retrieve a single product with prices and subscription information included in the result.
    price_kwargs is a list of filters provided to stripe.Price.list
    """
    product_future = executor.submit(stripe.Product.retrieve, product_id)
    price_kwargs = price_kwargs or {}
    prices = get_subscription_prices(user, product=product_id, **price_kwargs)
    product: ProductDetail = {
        **_minimize_product(product_future.result()),
        'prices': [_price_without_product(price) for price in prices],
        'subscription_info': {'sub_id': None, 'current_period_end': None, 'cancel_at': None},
    }
    for price in prices:
        if price['subscription_info']['sub_id']:
            product['subscription_info'] = price['subscription_info']
    return product


# Setup Intents
@customer_id_required
def create_setup_intent(user: UserProtocol, payment_method_types: Optional[List[PaymentMethodType]] = None,
                        **kwargs) -> stripe.SetupIntent:
    """
     Create a setup intent, the first step in adding a payment method which can later be used for paying subscriptions.
     payment_method_types restricts allowed methods via Stripe allowed_payment_method_types.
     If omitted, payment methods are managed through the Stripe Dashboard.
     kwargs contains additional parameters provided to stripe.SetupIntent.create

     Raises an exception if the user does not have a customer id
     """
    setup_intent_kwargs: Dict[str, Any] = {
        'customer': user.stripe_customer_id,
        'confirm': False,
        'usage': "off_session"}
    if payment_method_types is not None:
        if 'allowed_payment_method_types' in kwargs:
            raise TypeError('Pass either payment_method_types or allowed_payment_method_types, not both.')
        setup_intent_kwargs['allowed_payment_method_types'] = payment_method_types
    setup_intent_kwargs.update(kwargs)
    return stripe.SetupIntent.create(**setup_intent_kwargs)


# Payment Methods
def list_payment_methods(user: Optional[UserProtocol], types: List[PaymentMethodType],
                         **kwargs) -> Generator[stripe.PaymentMethod, None, None]:
    """
    List all payment methods for a user.
    Stripe only allows to retrieve payment methods for a single type at a time.
    This functions gathers payment methods from multiple types by making parallel requests to the Stripe API.
    kwargs is additional filters to pass to stripe.PaymentMethod.list
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


def detach_payment_method(user: Optional[UserProtocol], payment_method_id: str) -> stripe.PaymentMethod:
    """
    Detach a user's payment method.
    It is needed to retrieve the payment method first to check the customer id.
    If a customer attempts to detach an object belonging to another customer, StripeWrongCustomer exception is raised.
    """
    obj = retrieve(user, stripe.PaymentMethod, payment_method_id, action="detach")
    return stripe.PaymentMethod.detach(obj["id"])


def detach_all_payment_methods(user: Optional[UserProtocol], types: List[PaymentMethodType],
                               **kwargs) -> List[stripe.PaymentMethod]:
    """
    Detach all of a user's payment methods.
    """
    if user and user.stripe_customer_id:
        futures = [executor.submit(stripe.PaymentMethod.detach,
                                   payment_type["id"])
                   for payment_type in list_payment_methods(user, types, **kwargs)]
        return [f.result() for f in futures]
    return []
