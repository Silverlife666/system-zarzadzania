"""Serializacja danych sesji przypisanych do order_id."""

from __future__ import annotations

from datetime import date, datetime
import base64
from typing import Any

import pandas as pd


UNSERIALIZABLE_CONTEXT = object()


def serialize_context_value(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        return {
            "__context_type__": "dataframe",
            "records": serialize_context_value(value.to_dict("records")),
        }
    if isinstance(value, datetime):
        return {"__context_type__": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"__context_type__": "date", "value": value.isoformat()}
    if isinstance(value, (bytes, bytearray)):
        return {"__context_type__": "bytes", "value": base64.b64encode(value).decode("ascii")}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            encoded = serialize_context_value(item)
            if encoded is not UNSERIALIZABLE_CONTEXT:
                result[str(key)] = encoded
        return result
    if isinstance(value, (list, tuple)):
        result = []
        for item in value:
            encoded = serialize_context_value(item)
            if encoded is not UNSERIALIZABLE_CONTEXT:
                result.append(encoded)
        return result
    if hasattr(value, "item"):
        try:
            return serialize_context_value(value.item())
        except (TypeError, ValueError):
            pass
    return UNSERIALIZABLE_CONTEXT


def deserialize_context_value(value: Any) -> Any:
    if isinstance(value, dict) and value.get("__context_type__") == "dataframe":
        return pd.DataFrame(deserialize_context_value(value.get("records", [])))
    if isinstance(value, dict) and value.get("__context_type__") == "datetime":
        return datetime.fromisoformat(value["value"])
    if isinstance(value, dict) and value.get("__context_type__") == "date":
        return date.fromisoformat(value["value"])
    if isinstance(value, dict) and value.get("__context_type__") == "bytes":
        return base64.b64decode(value["value"])
    if isinstance(value, dict):
        return {key: deserialize_context_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [deserialize_context_value(item) for item in value]
    return value
