import sys
from typing import Any, Optional


py38 = sys.version_info >= (3, 8)


if py38:
    from typing import Protocol
else:
    from typing_extensions import Protocol


class UserProtocol(Protocol):
    id: Any
    email: str
    stripe_customer_id: Optional[str]


class CacheProtocol(Protocol):
    def set(self, key: str, value: Any) -> Any:
        pass

    def get(self, key: str) -> Any:
        pass
