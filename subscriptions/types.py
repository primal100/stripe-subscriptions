import sys
from typing import Any, Optional


py38 = sys.version_info >= (3, 8)


if py38:
    from typing import Protocol, Literal
else:
    from typing_extensions import Protocol, Literal


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


class CacheProtocol(Protocol):
    def set(self, key: str, value: Any) -> Any:
        pass

    def get(self, key: str) -> Any:
        pass
