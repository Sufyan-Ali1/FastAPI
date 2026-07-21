"""services/exceptions.py - DOMAIN errors (not HTTP errors).

Services raise these HTTP-agnostic errors; the API layer translates them into
HTTP responses (see app/main.py). This keeps business logic reusable outside
of HTTP (background tasks, WebSockets, CLI).
"""


class ItemNotFoundError(Exception):
    def __init__(self, item_id: int):
        self.item_id = item_id
        super().__init__(f"Item {item_id} not found")


class DuplicateSKUError(Exception):
    def __init__(self, sku: str):
        self.sku = sku
        super().__init__(f"SKU '{sku}' already exists")
