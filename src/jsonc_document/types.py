"""Public recursive types for decoded JSONC values."""

type Scalar = str | int | float | bool | None
"""A decoded string, number, Boolean, or null value."""

type Value = Scalar | list[Value] | dict[str, Value]
"""A decoded scalar or recursively nested JSONC collection."""
