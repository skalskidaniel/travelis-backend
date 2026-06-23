import re
from decimal import Decimal
from datetime import datetime, date
from enum import Enum
from typing import Any, Generator, Iterable, TypeVar

from core.models.common import BoardType, ProviderName

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATETIME_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$"
)
BATCH_WRITE_LIMIT = 25
BATCH_READ_LIMIT = 100

T = TypeVar("T")


def float_to_decimal(val: float) -> Decimal:
    """Converts a float to a Decimal via string representation to avoid precision artifacts."""
    return Decimal(str(val))


def decimal_to_float(val: Decimal) -> float:
    """Converts a Decimal to a float."""
    return float(val)


def strip_none_values(d: dict[str, Any]) -> dict[str, Any]:
    """Recursively removes all keys with None values from a dictionary."""
    result = {}
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, dict):
            result[k] = strip_none_values(v)
        elif isinstance(v, list):
            result[k] = [strip_none_values(i) if isinstance(i, dict) else i for i in v]
        else:
            result[k] = v
    return result


def serialize_item(val: Any) -> Any:
    """Recursively converts Python types into DynamoDB-compatible types."""
    if isinstance(val, dict):
        return {k: serialize_item(v) for k, v in val.items() if v is not None}
    elif isinstance(val, (list, tuple, set, frozenset)):
        return [serialize_item(i) for i in val if i is not None]
    elif isinstance(val, float):
        return float_to_decimal(val)
    elif isinstance(val, (datetime, date)):
        return val.isoformat()
    elif isinstance(val, Enum):
        return val.value
    elif isinstance(val, Decimal):
        return val
    elif hasattr(val, "unicode_string"):
        return str(val)
    else:
        return val


def deserialize_item(val: Any) -> Any:
    """Recursively converts DynamoDB types (like Decimals) back to standard Python types."""
    if isinstance(val, dict):
        return {k: deserialize_item(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [deserialize_item(i) for i in val]
    elif isinstance(val, Decimal):
        if val % 1 == 0:
            return int(val)
        return float(val)
    elif isinstance(val, str):
        if DATETIME_PATTERN.match(val):
            try:
                return datetime.fromisoformat(val)
            except ValueError:
                pass
        if DATE_PATTERN.match(val):
            try:
                return date.fromisoformat(val)
            except ValueError:
                pass
        try:
            return BoardType(val)
        except ValueError:
            pass
        try:
            return ProviderName(val)
        except ValueError:
            pass
        return val
    else:
        return val


def chunked(iterable: Iterable[T], size: int) -> Generator[list[T], None, None]:
    """Chunks an iterable into lists of a given size."""
    chunk = []
    for item in iterable:
        chunk.append(item)
        if len(chunk) == size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk
