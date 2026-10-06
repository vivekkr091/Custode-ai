"""Condition evaluation logic for policy rules.

Strictly deterministic and safe: no eval(), exec(), or arbitrary code execution.
"""

from typing import Any, Union
import uuid

from app.schemas.policy import ActionContext, PolicyRuleCondition, RuleOperator


def _is_numeric(value: Any) -> bool:
    """Check if value is numeric or can be safely cast to float."""
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        try:
            float(value)
            return True
        except ValueError:
            return False
    return False


def _to_float(value: Any) -> float:
    """Convert value to float safely."""
    return float(value)


def _normalize_string(value: Any) -> str:
    """Convert value to string for string/UUID comparisons."""
    if isinstance(value, uuid.UUID):
        return str(value).lower()
    return str(value)


def evaluate_condition(condition: Union[PolicyRuleCondition, dict], context: ActionContext) -> bool:
    """Evaluate a single rule condition against an ActionContext.

    Returns True if condition matches, False otherwise.
    Never throws exceptions on type mismatches: safely returns False.
    """
    if isinstance(condition, dict):
        field_name = condition.get("field", "")
        operator = condition.get("operator", "")
        target_value = condition.get("value")
    else:
        field_name = condition.field
        operator = condition.operator
        target_value = condition.value

    context_value = context.get_field(field_name)

    # 1. Operators eq and neq
    if operator == RuleOperator.eq.value:
        if context_value is None:
            return target_value is None or target_value == "null"
        if target_value is None:
            return False
        # If both numeric, compare as floats
        if _is_numeric(context_value) and _is_numeric(target_value):
            return _to_float(context_value) == _to_float(target_value)
        # Normal string comparison (case-insensitive for UUIDs)
        ctx_str = _normalize_string(context_value)
        tgt_str = _normalize_string(target_value)
        if field_name.endswith(".id"):
            return ctx_str.lower() == tgt_str.lower()
        return ctx_str == tgt_str

    if operator == RuleOperator.neq.value:
        if context_value is None:
            return target_value is not None and target_value != "null"
        if target_value is None:
            return True
        if _is_numeric(context_value) and _is_numeric(target_value):
            return _to_float(context_value) != _to_float(target_value)
        ctx_str = _normalize_string(context_value)
        tgt_str = _normalize_string(target_value)
        if field_name.endswith(".id"):
            return ctx_str.lower() != tgt_str.lower()
        return ctx_str != tgt_str

    # 2. Null context check for remaining operators
    if context_value is None:
        if operator == RuleOperator.not_in.value:
            return True
        return False

    # 3. Numeric comparison operators
    if operator in (RuleOperator.gt.value, RuleOperator.gte.value, RuleOperator.lt.value, RuleOperator.lte.value):
        if not _is_numeric(context_value) or not _is_numeric(target_value):
            return False
        c_val = _to_float(context_value)
        t_val = _to_float(target_value)
        if operator == RuleOperator.gt.value:
            return c_val > t_val
        if operator == RuleOperator.gte.value:
            return c_val >= t_val
        if operator == RuleOperator.lt.value:
            return c_val < t_val
        if operator == RuleOperator.lte.value:
            return c_val <= t_val

    # 4. Collection membership operators
    if operator == RuleOperator.in_.value:
        if isinstance(target_value, (list, tuple, set)):
            ctx_str = _normalize_string(context_value)
            if field_name.endswith(".id"):
                targets = {_normalize_string(x).lower() for x in target_value}
                return ctx_str.lower() in targets
            targets = {_normalize_string(x) for x in target_value}
            return ctx_str in targets
        return False

    if operator == RuleOperator.not_in.value:
        if isinstance(target_value, (list, tuple, set)):
            ctx_str = _normalize_string(context_value)
            if field_name.endswith(".id"):
                targets = {_normalize_string(x).lower() for x in target_value}
                return ctx_str.lower() not in targets
            targets = {_normalize_string(x) for x in target_value}
            return ctx_str not in targets
        return True

    # 5. String matching operators
    ctx_str = _normalize_string(context_value)
    tgt_str = _normalize_string(target_value)

    if operator == RuleOperator.contains.value:
        return tgt_str in ctx_str

    if operator == RuleOperator.starts_with.value:
        return ctx_str.startswith(tgt_str)

    if operator == RuleOperator.ends_with.value:
        return ctx_str.endswith(tgt_str)

    return False
