from functools import wraps
from .exceptions import StripeCustomerIdRequired
from typing import Callable
from .types import UserProtocol


def customer_id_required(f: Callable):
    """
    Decorator to check if a user already has a customer id set.
    If not, StripeCustomerIdRequired is raised.
    To fix this call, create_customer first.
    """
    @wraps(f)
    def wrapper(user: UserProtocol, *args, **kwargs):
        if user and user.stripe_customer_id:
            return f(user, *args, **kwargs)
        raise StripeCustomerIdRequired(
            "It is required to first create this customer in stripe using the create_customer method, and save changes to the stripe_customer_id field")
    return wrapper

