import sys
from typing import Any, Optional, Dict, Sequence, List


py38 = sys.version_info >= (3, 8)


if py38:
    from typing import Protocol, Literal, TypedDict
else:
    from typing_extensions import Protocol, Literal, TypedDict


PaymentMethodType = Literal[
                            "acss_debit",
                            "afterpay_clearpay",
                            "alipay",
                            "au_becs_debit",
                            "bacs_debit",
                            "bancontact",
                            "card",
                            "card_present",
                            "eps",
                            "fpx",
                            "giropay",
                            "grabpay",
                            "ideal",
                            "interac_present",
                            "oxxo",
                            "p24",
                            "sepa_debit",
                            "sofort"
]


class UserProtocol(Protocol):
    id: Any
    email: str
    stripe_customer_id: Optional[str]


class ProductSubscription(TypedDict):
    sub_id: str
    product_id: str
    price_id: str
    cancel_at: int
    current_period_end: int


class ProductIsSubscribed(TypedDict):
    sub_id: Optional[str]
    product_id: Optional[str]
    price_id: Optional[str]
    cancel_at: Optional[int]
    current_period_end: Optional[int]


class SubscriptionInfo(TypedDict):
    sub_id: Optional[str]
    cancel_at: Optional[int]
    current_period_end: Optional[int]


class ProductPriceSubscription(ProductSubscription):
    subscription_info: SubscriptionInfo


class PriceNoProduct(TypedDict):
    id: str
    recurring: Dict[str, Any]
    type: str
    currency: str
    unit_amount: int
    unit_amount_decimal: float
    nickmame: str
    metadata: Dict[str, str]


class Price(PriceNoProduct):
    product: str


class PriceNoProductSubscriptionInfo(PriceNoProduct):
    subscription_info: SubscriptionInfo


class PriceSubscription(Price):
    subscription_info: SubscriptionInfo


class Product(TypedDict):
    id: str
    images: Sequence[str]
    type: str
    name: str
    shippable: bool
    unit_label: str
    url: str
    metadata: Dict[str, str]


class ProductDetail(Product):
    subscription_info: SubscriptionInfo
    prices: List[PriceNoProductSubscriptionInfo]
