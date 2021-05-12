class BaseStripeSubscriptionsError(BaseException):
    pass


class StripeCustomerIdRequired(BaseStripeSubscriptionsError):
    pass


class StripeWrongCustomer(BaseStripeSubscriptionsError):
    pass


class DefaultPaymentMethodRequired(BaseStripeSubscriptionsError):
    message = "set_as_default_payment_type is True but default_payment_method was not provided."
