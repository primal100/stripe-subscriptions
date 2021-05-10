class StripeCustomerIdRequired(BaseException):
    pass


class StripeWrongCustomer(BaseException):
    pass


class MissingArgsException(BaseException):
    pass


class SubscriptionArgsMissingException(BaseException):
    message = "It is required to provide either a product_id or a url"
