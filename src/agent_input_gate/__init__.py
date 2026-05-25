"""
agent-input-gate: composable rule-based input gating for LLM agents.

Gate agent inputs with rules before they reach the agent. Checks text (and
optional metadata) against rules like max length, blocked patterns, and keyword
topic filters. Returns a GateResult with pass/fail and violations.
"""

import re
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class GateResult:
    """Result of running an InputGate check."""

    passed: bool
    violations: list[str] = field(default_factory=list)
    # "pass", "warn", or "block"
    action_taken: str = "pass"


class InputBlockedError(Exception):
    """Raised when a gate check fails in block mode."""

    def __init__(self, violations: list[str]):
        self.violations = violations
        super().__init__(f"Input blocked: {'; '.join(violations)}")


class GateRule:
    """Base class for all gate rules."""

    def check(self, text: str, metadata: dict | None = None) -> list[str]:
        """Return a list of violation strings; empty list means the rule passed."""
        raise NotImplementedError


class MaxInputLength(GateRule):
    """Reject inputs that exceed a character-count ceiling."""

    def __init__(self, max_chars: int):
        self.max_chars = max_chars

    def check(self, text: str, metadata: dict | None = None) -> list[str]:
        length = len(text)
        if length > self.max_chars:
            return [f"Input too long: {length} chars, max {self.max_chars}"]
        return []


class BlockedPattern(GateRule):
    """Reject inputs that match any of the supplied regex patterns."""

    def __init__(self, *patterns: str, case_sensitive: bool = False):
        self.patterns = list(patterns)
        self.flags = 0 if case_sensitive else re.IGNORECASE

    def check(self, text: str, metadata: dict | None = None) -> list[str]:
        violations = []
        for pattern in self.patterns:
            if re.search(pattern, text, self.flags):
                violations.append(f"Blocked pattern matched: {pattern}")
        return violations


class RequiredMetadataKey(GateRule):
    """Require that specific keys are present in the metadata dict."""

    def __init__(self, *keys: str):
        self.keys = list(keys)

    def check(self, text: str, metadata: dict | None = None) -> list[str]:
        violations = []
        for key in self.keys:
            # metadata=None means all keys are missing
            if metadata is None or key not in metadata:
                violations.append(f"Required metadata key missing: {key}")
        return violations


class AllowedTopics(GateRule):
    """
    Keyword topic filter (no ML). Passes if at least `min_matches` of the
    supplied topic strings appear as case-insensitive substrings in the text.
    """

    def __init__(self, *topics: str, min_matches: int = 1):
        self.topics = list(topics)
        self.min_matches = min_matches

    def check(self, text: str, metadata: dict | None = None) -> list[str]:
        text_lower = text.lower()
        matched = sum(1 for t in self.topics if t.lower() in text_lower)
        if matched < self.min_matches:
            total = len(self.topics)
            return [
                f"Input does not match required topics (matched {matched}/{total})"
            ]
        return []


class InputGate:
    """
    Composable input gate that runs a list of GateRules against text (and
    optional metadata) before the input reaches an agent.

    action="block" (default): raises InputBlockedError on any violation.
    action="warn":  returns GateResult(passed=False, action_taken="warn").
    action="pass":  always returns GateResult(passed=True, action_taken="pass").
    """

    def __init__(
        self,
        rules: list[GateRule] | None = None,
        action: Literal["block", "warn", "pass"] = "block",
    ):
        self._rules: list[GateRule] = list(rules) if rules else []
        self._action = action

    def check(self, text: str, metadata: dict | None = None) -> GateResult:
        """Run all rules and return a GateResult (may raise InputBlockedError)."""
        violations: list[str] = []
        for rule in self._rules:
            violations.extend(rule.check(text, metadata))

        if not violations:
            return GateResult(passed=True, violations=[], action_taken=self._action)

        # There are violations — behaviour depends on action setting
        if self._action == "block":
            raise InputBlockedError(violations)
        if self._action == "warn":
            return GateResult(passed=False, violations=violations, action_taken="warn")
        # action == "pass": surface the violations but still report as passed
        return GateResult(passed=True, violations=violations, action_taken="pass")

    def gate(self, text: str, metadata: dict | None = None) -> str:
        """
        Convenience wrapper: call check() and return the text if it passed.
        Raises InputBlockedError when blocked.
        """
        result = self.check(text, metadata)
        if not result.passed and self._action == "warn":
            # warn mode: gate() passes through but result is accessible via check()
            return text
        # check() already raised for block mode; for pass mode we always get here
        return text

    def add_rule(self, rule: GateRule) -> "InputGate":
        """Append a rule and return self for chaining."""
        self._rules.append(rule)
        return self

    def remove_rule(self, index: int) -> "InputGate":
        """Remove the rule at position `index`. Raises IndexError for bad index."""
        if index < 0 or index >= len(self._rules):
            raise IndexError(f"Rule index {index} out of range (have {len(self._rules)} rules)")
        del self._rules[index]
        return self

    def rules(self) -> list[GateRule]:
        """Return a copy of the current rule list."""
        return list(self._rules)


__all__ = [
    "GateResult",
    "InputBlockedError",
    "GateRule",
    "MaxInputLength",
    "BlockedPattern",
    "RequiredMetadataKey",
    "AllowedTopics",
    "InputGate",
]
