Stripe-Subscriptions
--------------------

This library is designed to make it as easy as possible for python web developers to manage Stripe Subscriptions.

Almost all functions accept a user argument which would typically be an instant of an object created using ORM. This ensures that a user cannot access data belonging to another user. An exception will be raised if a function is called with a user who does not own the object being retrieved, updated or deleted. List functions will only return objects belonging to the user.
 
The sister library `django_stripe` implements this logic in a django app. This library is the non-django specific code from that library put here so it can be used as the base for implementations in other frameworks.

Getting Started:
----------------

To install:

```shell
pip install stripe_subscriptions
```

To get started you must have a ```User``` object which implements the ```stripe_customer_id``` argument for storing the customer ID in Stripe.

For example in Django:

```python
from django.db.contrib.auth import User
from django.db import models


class StripeUser(User):
    stripe_customer_id = models.CharField(max_length=255)

```

If you already have a field for storing a customer id or prefer a different fieldname, you can add a property:

```python
from django.db.contrib.auth import User
from django.db import models


class StripeUser(User):
    customer_id = models.CharField(max_length=255)

    @property
    def stripe_customer_id(self):
        return self.customer_id
```


Here are the available functions:


Manage Customer IDs
-------------------

```python
def create_customer(user: UserProtocol, **kwargs) -> stripe.Customer:
    """
    Creates a new customer over the stripe API using the user data. The customer id is set on the user object but not saved.
    The customer id must be saved to the database after this function is called.
    """

def delete_customer(user: UserProtocol) -> stripe.Customer:
    """
    Deletes a customer from Stripe. Sets the customer id on the user object to none but this is not saved.
    The customer id must be saved to the database after this function is called, e.g. by calling user.save().
    An exception will be raised if the user does already not have a customer id set.
    """

```

Create Checkouts
----------------

```python
def create_checkout(user: UserProtocol, mode: str, line_items: List[Dict[str, Any]] = None,
                    **kwargs) -> stripe.checkout.Session:
    """
    Creates a new Stripe checkout session for this user.
    Recommended to call create_subscription_checkout or create_setup_checkout instead.
    An exception will be raised if the user does already not have a customer id set.
    """


def create_subscription_checkout(user: UserProtocol, price_id: str, **kwargs) -> stripe.checkout.Session:
    """
    Creates a new Stripe subscription checkout session for this user for the given price.
    An exception will be raised if the user does already not have a customer id set.
    """


def create_setup_checkout(user: UserProtocol, subscription_id: str = None, **kwargs) -> stripe.checkout.Session:
    """
    Creates a new Stripe setup checkout session for this user, allowing them to add a new payment method for future use.
    An exception will be raised if the user does already not have a customer id set.
    """
```

Get Subscription Data
---------------------

```python
def list_subscriptions(user: Optional[UserProtocol], **kwargs) -> List[stripe.Subscription]:
    """
    List all subscriptions for a user. Filters can be applied with kwargs according to the Stripe API.
    """

def list_active_subscriptions(user: Optional[UserProtocol], **kwargs) -> List[stripe.Subscription]:
    """
    List all active subscriptions for a user.
    """
```

Products & Prices
-----------------

```python
def list_products_prices_subscribed_to(user: UserProtocol, **kwargs) -> List[ProductSubscription]:
    """
    Flat data for each active subscription to quickly check which products a user is subscribed to.
    """

def is_subscribed_and_cancelled_time(user: UserProtocol, product_id: Optional[str] = None,
                                     price_id: Optional[str] = None, **kwargs) -> ProductIsSubscribed:
    """
    Return first active subscription for a specific product or price or none to quickly check if a user is subscribed.
    """

def is_subscribed(user: UserProtocol, product_id: str = None, price_id: str = None) -> bool:
    """
    Returns a simple true or false to check if a user subscribed to the given product or price.
    """

def get_active_prices(**kwargs) -> List[Price]:
    """
    List all active prices
    """

def get_subscription_prices(user: Optional[UserProtocol] = None, **kwargs) -> List[PriceSubscription]:
    """
    Makes multiple requests to Stripe API to return the list of active prices with subscription data for each one for the given user.
    """

def retrieve_price(user: Optional[UserProtocol], price_id: str) -> PriceSubscription:
    """
    Retrieve a single price with subscription info
    """
```


