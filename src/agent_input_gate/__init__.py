"""
agent-input-gate: Gate agent inputs with composable rules.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

__version__ = "0.1.0"


@dataclass
class GateViolation:
    """A single failed rule.

    Attributes:
        rule: Name of the rule that failed.
        reason: Human-readable explanation of the failure.
        value: The input value that triggered the violation.
    """

    rule: str
    reason: str
    value: Any = None

    def __str__(self) -> str:
        return f"[{self.rule}] {self.reason}"


@dataclass
class GateResult:
    """The outcome of running every rule in a gate against a value.

    Truthiness mirrors :attr:`passed`, so a result can be used directly in a
    boolean context::

        if gate.run(message):
            ...  # all rules passed

    Attributes:
        passed: ``True`` only if no rule was violated.
        violations: Every :class:`GateViolation` collected during the run.
        value: The input value that was checked.
    """

    passed: bool
    violations: list[GateViolation] = field(default_factory=list)
    value: Any = None

    @property
    def ok(self) -> bool:
        """Alias for :attr:`passed`."""
        return self.passed

    def __bool__(self) -> bool:
        return self.passed


class InputGateError(Exception):
    """Raised by :meth:`InputGate.check` when a rule is violated.

    The offending :class:`GateViolation` is available on the ``violation``
    attribute.
    """

    def __init__(self, violation: GateViolation) -> None:
        self.violation = violation
        super().__init__(str(violation))


class InputGate:
    """
    Composable input validation gate for agent messages or arbitrary values.

    Rules are added via builder methods and checked in order.
    ``.check()`` raises InputGateError on first failure.
    ``.run()`` collects all violations.

    Usage::

        gate = InputGate()
        gate.add_max_length(1000)
        gate.add_no_pattern(r"ignore all previous", "prompt injection")
        gate.check(user_message)
    """

    def __init__(self) -> None:
        self._rules: list[tuple[str, Callable[[Any], Optional[str]]]] = []

    def add_rule(self, name: str, fn: Callable[[Any], Optional[str]]) -> "InputGate":
        """Add a custom rule. fn(value) returns error string or None."""
        self._rules.append((name, fn))
        return self

    def add_max_length(self, max_len: int) -> "InputGate":
        """Fail if ``len(str(value))`` is greater than ``max_len``."""
        def check(val: Any) -> Optional[str]:
            s = str(val) if not isinstance(val, str) else val
            if len(s) > max_len:
                return f"Input length {len(s)} exceeds max {max_len}"
            return None
        return self.add_rule("max_length", check)

    def add_min_length(self, min_len: int) -> "InputGate":
        """Fail if ``len(str(value))`` is less than ``min_len``."""
        def check(val: Any) -> Optional[str]:
            s = str(val) if not isinstance(val, str) else val
            if len(s) < min_len:
                return f"Input length {len(s)} below min {min_len}"
            return None
        return self.add_rule("min_length", check)

    def add_no_pattern(self, pattern: str, label: str = "", flags: int = re.IGNORECASE) -> "InputGate":
        """Fail if the regular expression ``pattern`` is found in the value.

        Matching is case-insensitive by default; pass ``flags=0`` for a
        case-sensitive match. ``label`` is used in the violation message and
        rule name when provided.
        """
        compiled = re.compile(pattern, flags)
        rule_name = f"no_pattern:{label or pattern[:20]}"
        def check(val: Any) -> Optional[str]:
            s = str(val) if not isinstance(val, str) else val
            if compiled.search(s):
                return f"Forbidden pattern matched: {label or pattern}"
            return None
        return self.add_rule(rule_name, check)

    def add_required_pattern(self, pattern: str, label: str = "", flags: int = re.IGNORECASE) -> "InputGate":
        """Fail unless the regular expression ``pattern`` is found in the value.

        Matching is case-insensitive by default; pass ``flags=0`` for a
        case-sensitive match.
        """
        compiled = re.compile(pattern, flags)
        rule_name = f"required_pattern:{label or pattern[:20]}"
        def check(val: Any) -> Optional[str]:
            s = str(val) if not isinstance(val, str) else val
            if not compiled.search(s):
                return f"Required pattern not found: {label or pattern}"
            return None
        return self.add_rule(rule_name, check)

    def add_not_empty(self) -> "InputGate":
        """Fail if the value is ``None`` or an empty ``str``/``list``/``dict``."""
        def check(val: Any) -> Optional[str]:
            if val is None or (isinstance(val, (str, list, dict)) and not val):
                return "Input must not be empty"
            return None
        return self.add_rule("not_empty", check)

    def add_no_keywords(self, keywords: list[str], case_sensitive: bool = False) -> "InputGate":
        """Fail if any of ``keywords`` appears as a substring of the value.

        Matching is case-insensitive unless ``case_sensitive`` is ``True``.
        """
        def check(val: Any) -> Optional[str]:
            s = str(val) if not isinstance(val, str) else val
            haystack = s if case_sensitive else s.lower()
            for kw in keywords:
                needle = kw if case_sensitive else kw.lower()
                if needle in haystack:
                    return f"Forbidden keyword: {kw}"
            return None
        return self.add_rule("no_keywords", check)

    def add_allowed_topics(self, topics: list[str], case_sensitive: bool = False) -> "InputGate":
        """Require that at least one of the allowed topics is mentioned."""
        def check(val: Any) -> Optional[str]:
            s = str(val) if not isinstance(val, str) else val
            haystack = s if case_sensitive else s.lower()
            for t in topics:
                needle = t if case_sensitive else t.lower()
                if needle in haystack:
                    return None
            return f"Input does not mention any allowed topic: {topics}"
        return self.add_rule("allowed_topics", check)

    def add_type_check(self, expected_type: type) -> "InputGate":
        """Fail unless the value is an instance of ``expected_type``."""
        def check(val: Any) -> Optional[str]:
            if not isinstance(val, expected_type):
                return f"Expected type {expected_type.__name__}, got {type(val).__name__}"
            return None
        return self.add_rule(f"type:{expected_type.__name__}", check)

    def check(self, value: Any) -> None:
        """Check value against all rules; raise InputGateError on first failure."""
        for name, fn in self._rules:
            error = fn(value)
            if error:
                raise InputGateError(GateViolation(rule=name, reason=error, value=value))

    def run(self, value: Any) -> GateResult:
        """Check all rules and return a GateResult with all violations."""
        violations: list[GateViolation] = []
        for name, fn in self._rules:
            error = fn(value)
            if error:
                violations.append(GateViolation(rule=name, reason=error, value=value))
        return GateResult(passed=not violations, violations=violations, value=value)

    def wrap(self) -> Callable[..., Any]:
        """Decorator: gate the first positional argument on each call."""
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            def wrapper(value: Any, *args: Any, **kwargs: Any) -> Any:
                self.check(value)
                return fn(value, *args, **kwargs)
            return wrapper
        return decorator


__all__ = [
    "InputGate",
    "InputGateError",
    "GateResult",
    "GateViolation",
    "__version__",
]
