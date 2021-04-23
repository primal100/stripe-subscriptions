def create_test_payment_method(user):
    if not user.stripe_customer_id:
        create_customer(user)
    payment_method = stripe.PaymentMethod.create(
        type="card",
        card={
            "number": "4242424242424242",
            "exp_month": 9,
            "exp_year": 2021,
            "cvc": "314",
        },
    )
    payment_method_id = payment_method['id']
    stripe.PaymentMethod.attach(payment_method_id, customer=user.stripe_customer_id)
    stripe.Customer.modify(user.stripe_customer_id, invoice_settings={'default_payment_method': payment_method_id})
    return payment_method
