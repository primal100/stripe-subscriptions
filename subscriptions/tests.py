import stripe
from .decorators import customer_id_required
from .types import UserProtocol


def create_payment_method(**kwargs):
    return stripe.PaymentMethod.create(
        type="card",
        card={
            "number": "4242424242424242",
            "exp_month": 9,
            "exp_year": 2025,
            "cvc": "314",
        },
        **kwargs
    )


@customer_id_required
def create_payment_method_for_customer(user: UserProtocol, **kwargs):
    payment_method = create_payment_method(**kwargs)
    payment_method_id = payment_method['id']
    stripe.PaymentMethod.attach(payment_method_id, customer=user.stripe_customer_id)
    return payment_method


def create_default_payment_method_for_customer(user: UserProtocol, **kwargs):
    payment_method = create_payment_method_for_customer(user, **kwargs)
    payment_method_id = payment_method['id']
    stripe.Customer.modify(user.stripe_customer_id,
                           invoice_settings={'default_payment_method': payment_method_id})
    return payment_method
