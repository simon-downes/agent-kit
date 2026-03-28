"""Filter parsing for post-processing database query results."""


def parse_filter(expr: str) -> tuple[str, str, str]:
    """Parse a filter expression into (key, operator, value).

    Supported formats:
        Key=Value       → equals
        Key!=Value      → not equals
        Key~=Value      → contains
    """
    for op in ("!=", "~=", "="):
        if op in expr:
            key, value = expr.split(op, 1)
            op_name = {"=": "=", "!=": "!=", "~=": "contains"}[op]
            return key.strip(), op_name, value.strip()

    raise ValueError(f"Invalid filter: {expr!r} (expected Key=Value, Key!=Value, or Key~=Value)")
