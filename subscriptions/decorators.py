from functools import wraps
from .exceptions import StripeCustomerIdRequired, StripeWrongCustomer
from .types import UserProtocol


def customer_id_required(f):
    @wraps(f)
    def wrapper(user: UserProtocol, *args, **kwargs):
        if user and user.stripe_customer_id:
            return f(user, *args, **kwargs)
        raise StripeCustomerIdRequired(
            "It is required to first create this customer in stripe using the create_customer method, and save changes to the stripe_customer_id field")
    return wrapper


def check_if_user_can_update(obj_class, action="update"):
    def _check_if_user_can_update(f):
        @wraps(f)
        @customer_id_required
        def wrapper(user: UserProtocol, obj_id: str, *args, **kwargs):
            obj = obj_class.retrieve(obj_id)
            if obj['customer'] != user.stripe_customer_id:
                msg = f"Customer {user.stripe_customer_id} cannot {action} {obj['object']} {obj_id} as they do not own it."
                raise StripeWrongCustomer(msg)
            return f(user, obj, *args, **kwargs)
        return wrapper
    return _check_if_user_can_update
