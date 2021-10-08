# Stripe Subscriptions

This library is designed to make it as easy as possible for python web developers to manage Stripe Subscriptions. It allows to create Stripe Checkouts and also contains functions to ease the creation of custom checkouts

Almost all functions accept a user argument which would typically be an instant of an object created using ORM. This ensures that a user cannot access data belonging to another user. An exception will be raised if a function is called with a user who does not own the object being retrieved, updated or deleted. List functions will only return objects belonging to the user.
 
The sister library `django_stripe` implements this logic in a django app. ```stripe-subscriptins``` is the non-django specific code from that library put here so it can be used as the base for implementations in other frameworks and ORMs.

## Getting Started:

To install:

```shell
pip install stripe_subscriptions
```

To get started you must have a ```User``` object which implements the ```email``` and ```stripe_customer_id``` properties.

For example in Django (```email``` property already exists):

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


## Example Usage

The easiest way to integrate with Stripe is to create a checkout. First create a product and price in the Stripe Dashboard and copy the price_id and your api keys.

```python
import stripe
import subscriptions
from django.contrib.auth.models import User     # Replace with appropriate ORM import

stripe.api_key = "sk_test_....."
price_id = "price_1JB9PtCz06et8VuzfLu1Z9bf"

user = User.objects.get(id=1)   # Replace with your ORM logic for retrieving a user

if not user.stripe_customer_id:
    subscriptions.create_customer(user)
    user.save()                 # Or however models can be saved in ORM
session = subscriptions.create_subscription_checkout(user, price_id)
session_id = session['id']
```

Return the session_id to the user (such as through an API or HTML template) and insert the following Javascript to redirect to the Stripe checkout:

```javascript
<script src="https://js.stripe.com/v3/"></script>
<script>
    var stripePublicKey = 'pk_test...';
    var sessionId = '{{ sessionId }}';
    
    var stripe = Stripe(stripePublicKey);
    stripe.redirectToCheckout({sessionId: sessionId})
</script>
````
To check if a user is subscribed to the product:

```python
import stripe
import subscriptions
from django.contrib.auth.models import User     # Replace with appropriate ORM import

stripe.api_key = "sk_test_....."
product_id = "prod_Jo3KY017h0SZ1x"

user = User.objects.get(id=1)   # Replace with your ORM logic for retrieving a user

if not user.stripe_customer_id:
    subscriptions.create_customer(user)
    user.save()                 # Or however models can be saved in ORM

is_subscribed = subscriptions.is_subscribed(user, product_id=product_id)
```
## Function Reference

### Manage Customer IDs

For more information see https://stripe.com/docs/api/customers
```python
from subscriptions import create_customer, delete_customer

def create_customer(user: UserProtocol, **kwargs) -> stripe.Customer:
    """
    Creates a new customer over the stripe API using the given user's data. The customer id is set on the user object but not saved.
    The customer id must be saved to the database after this function is called.
    """

def delete_customer(user: UserProtocol) -> stripe.Customer:
    """
    Deletes a customer from Stripe. Sets the customer id on the user object to none but this is not saved.
    The customer id must be saved to the database after this function is called, e.g. by calling user.save().
    An exception will be raised if the user does already not have a customer id set.
    """

```

### Create Stripe Checkouts


These functions create Stripe Checkouts sessions.

Use stripe.js to redirect to the given sessionId.

See here for more info:
https://stripe.com/docs/payments/checkout


```python
from subscriptions import create_checkout, create_subscription_checkout, create_setup_checkout

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

### Manage subscriptions


For more info see: https://stripe.com/docs/api/subscriptions


```python
from subscriptions import list_subscriptions, list_active_subscriptions, cancel_subscription, cancel_subscription_for_product, update_default_payment_method_all_subscriptions, modify_subscription, create_subscription

def list_subscriptions(user: Optional[UserProtocol], **kwargs) -> List[stripe.Subscription]:
    """
    List all subscriptions for a user. Filters can be applied with kwargs according to the Stripe API.
    """

def list_active_subscriptions(user: Optional[UserProtocol], **kwargs) -> List[stripe.Subscription]:
    """
    List all active subscriptions for a user.
    """
    
def cancel_subscription(user: UserProtocol, subscription_id: str) -> stripe.Subscription:
    """
    Allow a user to cancel their subscription.
    If a user attempts to cancel a subscription belonging to another customer, StripeWrongCustomer will be raised.
    """
    
def cancel_subscription_for_product(user: UserProtocol, product_id: str) -> bool:
    """
    Allow a user to cancel their subscription by the id of the product they are subscribed to, if such a subscription exists.
    Returns True if the subscription exists for that user, otherwise False.
    """

def update_default_payment_method_all_subscriptions(user: UserProtocol, default_payment_method: str) -> stripe.Customer:
    """
    Change the default payment method for the user and for all subscriptions belonging to that user.
    """
    
  
def modify_subscription(user: UserProtocol, subscription_id: str,
                        set_as_default_payment_method: bool = False, **kwargs) -> stripe.Subscription:
    """
    Modify a user's subscription
    kwargs is the parameters to modify.
    If payment_method is given in kwargs and set_as_default_payment_method is true, the default payment method is changed to that payment method for all subscriptions.
    Raises StripeWrongCustomer is a user tries to modify a subscription belonging to another customer.
    """
    
    
def create_subscription(user: UserProtocol, price_id: str,
                        set_as_default_payment_method: bool = False, **kwargs) -> stripe.Subscription:
    """
    Create a new subscription. A payment method must already be created.
    If set_as_default_payment_method is true, the given payment method will be set as the default for this customer.
    kwargs is a list of parameters to provide to stripe.Subscription.create in the Stripe API.
    """
```

### Products & Prices

Methods for viewing products and prices and checking if a user is subscribed to them. They can be created on the Stripe dashboard.


For more info see:
https://stripe.com/docs/billing/prices-guide



```python
from subscriptions import (list_products_prices_subscribed_to, is_subscribed_and_cancelled_time, is_subscribed, 
                           get_active_prices, get_subscription_prices, retrieve_price, get_active_products,
                           get_subscription_products_and_prices, retrieve_product)


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
        kwargs is a list of filters to provide to stripe.Price.list as in the Stripe API.
    """

def get_subscription_prices(user: Optional[UserProtocol] = None, **kwargs) -> List[PriceSubscription]:
    """
    Makes multiple requests to Stripe API to return the list of active prices with subscription data for each one for the given user.
        kwargs is a list of filters to provide to stripe.Price.list as in the Stripe API.
    """

    
def retrieve_price(user: Optional[UserProtocol], price_id: str) -> PriceSubscription:
    """
    Retrieve a single price with subscription info
    """

def get_active_products(**kwargs) -> List[Product]:
    """
    Get a list of active products with subscription information for the given user.
    kwargs is a list of filters to provide to stripe.Product.list as in Stripe API.
    """

def get_subscription_products_and_prices(user: Optional[UserProtocol] = None,
                                         price_kwargs: Optional[Dict[str, Any]] = None,
                                         **kwargs) -> List[ProductDetail]:
    """
    Get a list of active products with their prices and subscription information included in the result.
    kwargs is a list of filters product to stripe.Product.list.
    price_kwargs is a list of filters provided to stripe.Price.list
    """

def retrieve_product(user: Optional[UserProtocol], product_id: str,
                     price_kwargs: Optional[Dict[str, Any]] = None) -> ProductDetail:
    """
    Retrieve a single product with prices and subscription information included in the result.
    price_kwargs is a list of filters provided to stripe.Price.list
    """
```

### Setup Intents

Setup Intents are the first step to creating a paying method which can later be used for paying for subscriptions.

For more information see:
https://stripe.com/docs/api/setup_intents

```python
from subscriptions import create_setup_intent

def create_setup_intent(user: UserProtocol, payment_method_types: List[PaymentMethodType] = None,
                        **kwargs) -> stripe.SetupIntent:
    """
     Create a setup intent, the first step in adding a payment method which can later be used for paying subscriptions.
     price_kwargs is a list of filters provided to stripe.SetupIntent.create

     Raises an exception if the user does not have a customer id
     """
```

### Payment Methods

For more info on Payment Methods in Stripe see:
https://stripe.com/docs/payments/payment-methods


```python
from subscriptions import list_payment_methods, detach_payment_method, detach_all_payment_methods

def list_payment_methods(user: Optional[UserProtocol], types: List[PaymentMethodType],
                         **kwargs) -> Generator[stripe.PaymentMethod, None, None]:
    """
    List all payment methods for a user.
    Stripe only allows to retrieve payment methods for a single type at a time.
    This functions gathers payment methods from multiple types by making parallel requests to the Stripe API.
    kwargs is additional filters to pass to stripe.PaymentMethod.list
    """

def detach_payment_method(user: Optional[UserProtocol], payment_method_id: str) -> stripe.PaymentMethod:
    """
    Detach a user's payment method.
    It is needed to retrieve the payment method first to check the customer id.
    If a customer attempts to detach an object belonging to another customer, StripeWrongCustomer exception is raised.
    """

def detach_all_payment_methods(user: Optional[UserProtocol], types: List[PaymentMethodType],
                               **kwargs) -> List[stripe.PaymentMethod]:
    """
    Detach all of a user's payment methods.
    """
```


### Generic Methods for Interacting with Stripe API

These functions mirror the retrieve, delete and modify methods of Stripe resources, but also check that the user owns the requested object. An exception will be raised otherwise. 

```python
from subscriptions import retrieve, delete, modify


def retrieve(user: UserProtocol, obj_cls, obj_id: str, action="retrieve") -> Mapping[str, Any]:
    """
    Retrieve an object over Stripe API for the given obj_id and obj_cls.
    obj_cls could be stripe.Subscription, stripe.PaymentMethod, stripe.Invoice, etc.
    If a customer attempts to retrieve an object belonging to another customer, StripeWrongCustomer exception is raised.
    The action word if provided is included in StripeWrongCustomer exception if raised.
    """

def delete(user: UserProtocol, obj_cls, obj_id: str, action: str = "delete"):
    """
    Delete an object over Stripe API with given obj_id for obj_cls.
    obj_cls could be stripe.Subscription, stripe.PaymentMethod, stripe.Invoice, etc.
    It is needed to retrieve the obj first to check the customer id.
    If a customer attempts to delete an object belonging to another customer, StripeWrongCustomer exception is raised.
    The action word if provided is included in StripeWrongCustomer exception if raised.
    """

def modify(user: UserProtocol, obj_cls, obj_id: str, action: str = "modify",
           **kwargs) -> Union[Mapping[str, Any], stripe.Subscription]:
    """
    Modify an object over Stripe API with given obj_id for obj_cls.
    obj_cls could be stripe.Subscription, stripe.PaymentMethod, stripe.Invoice, etc.
    It is needed to retrieve the obj first to check the customer id.
    If a customer attempts to modify an object belonging to another customer, StripeWrongCustomer exception is raised.
    kwargs are the parameters to be modified.
    The action word if provided is included in StripeWrongCustomer exception if raised.
    """
```


