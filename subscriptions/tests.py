import stripe
from .decorators import customer_id_required
from .types import UserProtocol


@customer_id_required
def create_payment_method_for_customer(user: UserProtocol, **kwargs) -> stripe.PaymentMethod:
    """
    Create a payment method for testing and attach to the given user.
    """
    return stripe.PaymentMethod.attach("pm_card_visa", customer=user.stripe_customer_id)


def create_default_payment_method_for_customer(user: UserProtocol, **kwargs) -> stripe.PaymentMethod:
    """
     Create a payment method for testing, attach to the given user, and set as the default.
     """
    payment_method = create_payment_method_for_customer(user, **kwargs)
    payment_method_id = payment_method['id']
    stripe.Customer.modify(user.stripe_customer_id,
                           invoice_settings={'default_payment_method': payment_method_id})
    return payment_method
