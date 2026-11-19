from enum import StrEnum


class ShoppingListStatus(StrEnum):
    DRAFT = "draft"
    TO_CHECK = "to_check"
    VALIDATED = "validated"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class SupplierType(StrEnum):
    STORE = "store"
    PRODUCER = "producer"
    ONLINE = "online"
    OTHER = "other"


class ShoppingWarningCode(StrEnum):
    UNIT_MISMATCH = "unit_mismatch"
    DUPLICATE_NAME = "duplicate_name"
    EMPTY_PROJECTION = "empty_projection"
