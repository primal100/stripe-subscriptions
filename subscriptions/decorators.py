from functools import wraps
from .exceptions import StripeCustomerIdRequired
from .types import UserProtocol


def customer_id_required(f):
    @wraps(f)
    def wrapper(user: UserProtocol, *args, **kwargs):
        if user.stripe_customer_id:
            return f(user, *args, **kwargs)
        raise StripeCustomerIdRequired(
            "It is required to first create this customer in stripe using the create_customer method")
    return wrapper