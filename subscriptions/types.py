from typing import Any, Optional, Dict, Sequence, List, TypeVar, Protocol, Literal, TypedDict


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
    product_id: Optional[str]
    price_id: Optional[str]
    cancel_at: Optional[int]
    current_period_end: Optional[int]


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
    recurring: Optional[Dict[str, Any]]
    type: str
    currency: str
    unit_amount: Optional[int]
    unit_amount_decimal: Optional[str]
    nickname: Optional[str]
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
    shippable: Optional[bool]
    unit_label: Optional[str]
    url: Optional[str]
    metadata: Dict[str, str]


class ProductDetail(Product):
    subscription_info: SubscriptionInfo
    prices: List[PriceNoProductSubscriptionInfo]


ResourceT_co = TypeVar('ResourceT_co', covariant=True)


class RetrievableResource(Protocol[ResourceT_co]):
    def retrieve(self, *args: Any, **kwargs: Any) -> ResourceT_co: ...


class ModifiableResource(RetrievableResource[ResourceT_co], Protocol[ResourceT_co]):
    def modify(self, *args: Any, **kwargs: Any) -> ResourceT_co: ...


class DeletableResource(RetrievableResource[ResourceT_co], Protocol[ResourceT_co]):
    def delete(self, *args: Any, **kwargs: Any) -> ResourceT_co: ...
