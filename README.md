# Stripe Subscriptions

This library is designed to make it as easy as possible for python web developers to manage Stripe Subscriptions. It allows to create Stripe Checkouts and also contains functions to ease the creation of custom checkouts

Almost all functions accept a user argument which would typically be an instant of an object created using ORM. This ensures that a user cannot access data belonging to another user. An exception will be raised if a function is called with a user who does not own the object being retrieved, updated or deleted. List functions will only return objects belonging to the user.
 
The sister library `django_stripe` implements this logic in a django app. ```stripe-subscriptins``` is the non-django specific code from that library put here so it can be used as the base for implementations in other frameworks and ORMs.

## Getting Started:

To install:

```shell
pip install stripe-subscriptions
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
session = subscriptions.create_subscription_checkout(
    user,
    price_id,
    success_url="https://example.com/success",
    cancel_url="https://example.com/cancel",
)
response_data = {
    "session_id": session.id,
    "checkout_url": session.url,
}
# Return response_data as JSON using your web framework.
```

For Stripe-hosted Checkout, return both `session_id` and `checkout_url` from your backend. After parsing that JSON response as `checkout`, redirect the browser directly to the full URL:

```javascript
window.location.assign(checkout.checkout_url);
```

Stripe.js and a publishable key are not needed for this redirect. Stripe removed `stripe.redirectToCheckout`; see the [migration guidance](https://docs.stripe.com/changelog/clover/2025-09-30/remove-redirect-to-checkout). The session ID can remain in the response for existing consumers, but the redirect uses `checkout_url`.

All three Checkout helpers already return the full `stripe.checkout.Session` with its `id` and `url`; no new return type or extra Stripe request is needed. This redirect flow applies to hosted Checkout. Embedded or custom Checkout uses its own frontend integration and can return a null `url`.

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


These functions create Stripe Checkouts sessions. Checkout payment methods are managed in the Stripe Dashboard; do not pass `payment_method_types`. For setup-mode Checkout sessions, pass a currency, for example `create_setup_checkout(user, currency="usd", success_url="https://example.com/success")`.

These helpers return the complete `stripe.checkout.Session`. For hosted Checkout, include `session.id` and `session.url` in your backend response and redirect the browser to `session.url`, as shown above. This also applies to setup-mode Checkout.

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

Functions for viewing products and prices and checking if a user is subscribed to them. They can be created on the Stripe dashboard.


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

Setup Intents are the first step to creating a paying method which can later be used for paying for subscriptions. The helper maps `payment_method_types` to Stripe's `allowed_payment_method_types` parameter. Omit it to use Dashboard-managed payment methods.

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

For more info on Payment Methods in Stripe see: https://stripe.com/docs/payments/payment-methods


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


### Generic Functions for Interacting with Stripe API

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


## Advanced

### Creating subscriptions in a custom checkout

To create a new subscription generally requires three steps:

1) Create a setup intent server-side and return the ```client_secret``` to the client
2) Use stripe.js (or equivalent for the client's platform) on the client to create the payment method with the ```client_secret```
3) Create a subscription server side with the new payment method id and ```price_id``` to subscribe to.


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

setup_intent = subscriptions.create_setup_intent(user)
return setup_intent['client_secret']

```
Supply the ```client_secret``` to the client either through API response or HTML template and create the payment method when the user submits their card details:


```javascript
<div id="card-element"></div>
<button id="subscribe-button" type="submit">Subscribe</button>

<script src="https://js.stripe.com/v3/"></script>
<script>
    var stripePublicKey = 'pk_test...';
    var client_secret = '{{ client_secret }}';
    var hidePostalCode = true;
    
    var stripe = Stripe(stripePublicKey);
    const elements = stripe.elements();
    const card = elements.create('card', {hidePostalCode: hidePostalCode});
    card.mount('#card-element');
    
    document.querySelector('#subscribe-button').addEventListener("click", () => {
        stripe
            .confirmCardSetup(client_secret, {
                payment_method: {
                    card: cardElement,
                },
            }).then(function (result) {
                var paymentMethodId = paymentMethod['id'];
                // Send request to create subscription to server with payment method
            });
    });
    
</script>
````

For more information on using Stripe Elements to collect the card details see: https://stripe.com/docs/stripe-js

Now, send the payment to the server (such as through a REST API post request) and create the subscription:

```python
import stripe
import subscriptions
from django.contrib.auth.models import User     # Replace with appropriate ORM import

stripe.api_key = "sk_test_....."
price_id = "price_1JB9PtCz06et8VuzfLu1Z9bf"
payment_method_id = "pm_1JiHZ7Cz06et8VuzwI1HftWk"  # Retrieved from API

user = User.objects.get(id=1)   # Replace with your ORM logic for retrieving a user

return subscriptions.create_subscription(user, price_id, default_payment_method=payment_method_id)

```

## Development and testing

Requires Python 3.11 or newer. Runtime dependencies and package metadata are declared in `pyproject.toml`.

Install the test tools with the Stripe SDK version used by CI:

```shell
python -m pip install -c constraints-ci.txt ".[test]"
```

Run offline tests and type checks without a Stripe key:

```shell
python -m pytest tests/test_stripe_resources.py -q
python -m mypy
```

Integration tests create and delete resources in Stripe test mode. Set `STRIPE_TEST_SECRET_KEY` in your environment, then run:

```shell
python -m pytest tests/test_subscriptions.py -vv
```

CI runs offline checks on Python 3.11 through 3.15 for pull requests and pushes. Stripe integration tests run on pushes to `master` and manual workflow runs when the test-key secret is configured. Each test customer has a unique email so overlapping runs do not share customers.

The Stripe dependency requirement is `>=16`, with no upper version limit. CI uses the exact version in `constraints-ci.txt`; validate SDK upgrades with the integration suite before updating that constraint.

Build and validate the wheel and source distribution:

```shell
python -m pip install build twine
python -m build
python -m twine check dist/*
```

## Publishing a release

Start from the merged release commit and set a new, unpublished version in `subscriptions/__version__.py`. Commit that version change and ensure CI passes before publishing. The scripts build the current checkout; they do not switch branches, update the version, commit, or tag it.

Install the publishing tools into your active Python 3.11+ environment:

```shell
python -m pip install --upgrade build twine
```

PowerShell:

```powershell
.\publish.ps1 -BuildOnly
.\publish.ps1 -Repository testpypi
.\publish.ps1
```

Bash:

```bash
./publish.sh --build-only
./publish.sh --repository testpypi
./publish.sh
```

Each invocation builds and strictly validates one wheel and one source distribution in a fresh `dist/release-*` directory, avoiding old artifacts. Build-only mode does not upload anything. Without that option, the default destination is **PyPI**; `testpypi` selects TestPyPI instead.

Use `-Python PATH` or `--python PATH` to select an interpreter; otherwise PowerShell uses `python` and Bash uses `python3`. Supply the destination's API token at Twine's password prompt, or use its `TWINE_PASSWORD` environment variable in automation. PyPI and TestPyPI use separate accounts/tokens. Do not commit credentials. Published distribution filenames cannot be reused; choose a new version for subsequent releases.
