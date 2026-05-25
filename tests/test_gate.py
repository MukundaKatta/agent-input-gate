"""Tests for agent_input_gate."""

import pytest

from agent_input_gate import (
    AllowedTopics,
    BlockedPattern,
    InputBlockedError,
    InputGate,
    MaxInputLength,
    RequiredMetadataKey,
)

# ---------------------------------------------------------------------------
# MaxInputLength
# ---------------------------------------------------------------------------


def test_max_length_under_limit_passes():
    rule = MaxInputLength(100)
    assert rule.check("hello") == []


def test_max_length_exactly_at_limit_passes():
    rule = MaxInputLength(5)
    assert rule.check("abcde") == []


def test_max_length_over_limit_violation():
    rule = MaxInputLength(5)
    violations = rule.check("toolongtext")
    assert len(violations) == 1
    assert "11 chars" in violations[0]
    assert "max 5" in violations[0]


def test_max_length_violation_message_format():
    rule = MaxInputLength(3)
    violations = rule.check("hello")
    assert violations[0] == "Input too long: 5 chars, max 3"


# ---------------------------------------------------------------------------
# BlockedPattern
# ---------------------------------------------------------------------------


def test_blocked_pattern_no_match_passes():
    rule = BlockedPattern(r"\bspam\b")
    assert rule.check("hello world") == []


def test_blocked_pattern_match_produces_violation():
    rule = BlockedPattern(r"\bspam\b")
    violations = rule.check("this is spam content")
    assert len(violations) == 1
    assert r"\bspam\b" in violations[0]


def test_blocked_pattern_case_insensitive_by_default():
    rule = BlockedPattern("forbidden")
    assert rule.check("FORBIDDEN text") != []


def test_blocked_pattern_case_sensitive_misses_wrong_case():
    rule = BlockedPattern("forbidden", case_sensitive=True)
    assert rule.check("FORBIDDEN text") == []


def test_blocked_pattern_case_sensitive_exact_case_matches():
    rule = BlockedPattern("forbidden", case_sensitive=True)
    assert rule.check("forbidden text") != []


def test_blocked_pattern_multiple_patterns_one_violation_each():
    rule = BlockedPattern("spam", "hate")
    violations = rule.check("spam and hate here")
    assert len(violations) == 2


def test_blocked_pattern_only_matching_patterns_flagged():
    rule = BlockedPattern("spam", "hate")
    violations = rule.check("only spam here")
    assert len(violations) == 1
    assert "spam" in violations[0]


# ---------------------------------------------------------------------------
# RequiredMetadataKey
# ---------------------------------------------------------------------------


def test_required_metadata_all_present_passes():
    rule = RequiredMetadataKey("user_id", "session")
    assert rule.check("hello", {"user_id": "123", "session": "abc"}) == []


def test_required_metadata_missing_key_violation():
    rule = RequiredMetadataKey("user_id")
    violations = rule.check("hello", {})
    assert len(violations) == 1
    assert "user_id" in violations[0]


def test_required_metadata_none_metadata_all_missing():
    rule = RequiredMetadataKey("user_id", "session")
    violations = rule.check("hello", None)
    assert len(violations) == 2
    keys_mentioned = " ".join(violations)
    assert "user_id" in keys_mentioned
    assert "session" in keys_mentioned


def test_required_metadata_partial_missing_reports_only_missing():
    rule = RequiredMetadataKey("a", "b", "c")
    violations = rule.check("hello", {"a": 1, "c": 3})
    assert len(violations) == 1
    assert "b" in violations[0]


# ---------------------------------------------------------------------------
# AllowedTopics
# ---------------------------------------------------------------------------


def test_allowed_topics_topic_found_passes():
    rule = AllowedTopics("weather", "forecast")
    assert rule.check("what is the weather today?") == []


def test_allowed_topics_no_match_violation():
    rule = AllowedTopics("weather")
    violations = rule.check("tell me a joke")
    assert len(violations) == 1
    assert "matched 0/1" in violations[0]


def test_allowed_topics_min_matches_not_reached_violation():
    rule = AllowedTopics("weather", "forecast", "rain", min_matches=2)
    violations = rule.check("what is the weather?")  # only 1 of 3 matches
    assert len(violations) == 1
    assert "matched 1/3" in violations[0]


def test_allowed_topics_min_matches_met_passes():
    rule = AllowedTopics("weather", "forecast", min_matches=2)
    assert rule.check("weather forecast for tomorrow") == []


def test_allowed_topics_case_insensitive():
    rule = AllowedTopics("Weather")
    assert rule.check("WEATHER update") == []


# ---------------------------------------------------------------------------
# InputGate — basic behaviour
# ---------------------------------------------------------------------------


def test_empty_gate_always_passes():
    gate = InputGate()
    result = gate.check("anything goes")
    assert result.passed is True
    assert result.violations == []


def test_gate_block_action_raises_on_violation():
    gate = InputGate(rules=[MaxInputLength(3)], action="block")
    with pytest.raises(InputBlockedError) as exc_info:
        gate.check("toolong")
    assert len(exc_info.value.violations) == 1


def test_gate_warn_action_returns_failed_result_without_raising():
    gate = InputGate(rules=[MaxInputLength(3)], action="warn")
    result = gate.check("toolong")
    assert result.passed is False
    assert result.action_taken == "warn"
    assert len(result.violations) == 1


def test_gate_pass_action_always_returns_passed():
    gate = InputGate(rules=[MaxInputLength(3)], action="pass")
    result = gate.check("toolong")
    assert result.passed is True
    assert result.action_taken == "pass"


def test_gate_multiple_violations_collected():
    gate = InputGate(
        rules=[MaxInputLength(3), BlockedPattern("bad")],
        action="warn",
    )
    result = gate.check("bad long input")
    assert len(result.violations) == 2


# ---------------------------------------------------------------------------
# InputBlockedError
# ---------------------------------------------------------------------------


def test_input_blocked_error_violations_populated():
    err = InputBlockedError(["violation one", "violation two"])
    assert err.violations == ["violation one", "violation two"]
    assert "violation one" in str(err)
    assert "violation two" in str(err)


# ---------------------------------------------------------------------------
# gate() convenience method
# ---------------------------------------------------------------------------


def test_gate_method_returns_text_on_pass():
    gate = InputGate(rules=[MaxInputLength(100)])
    result = gate.gate("hello")
    assert result == "hello"


def test_gate_method_raises_on_block():
    gate = InputGate(rules=[MaxInputLength(3)], action="block")
    with pytest.raises(InputBlockedError):
        gate.gate("toolong")


def test_gate_method_passes_through_on_warn():
    gate = InputGate(rules=[MaxInputLength(3)], action="warn")
    result = gate.gate("toolong")
    assert result == "toolong"


# ---------------------------------------------------------------------------
# add_rule / remove_rule / rules()
# ---------------------------------------------------------------------------


def test_add_rule_returns_self_for_chaining():
    gate = InputGate()
    returned = gate.add_rule(MaxInputLength(10))
    assert returned is gate


def test_add_rule_appends_rule():
    gate = InputGate()
    gate.add_rule(MaxInputLength(10))
    assert len(gate.rules()) == 1


def test_remove_rule_removes_correct_index():
    r1 = MaxInputLength(10)
    r2 = MaxInputLength(20)
    gate = InputGate(rules=[r1, r2])
    gate.remove_rule(0)
    remaining = gate.rules()
    assert len(remaining) == 1
    assert remaining[0] is r2


def test_remove_rule_raises_index_error():
    gate = InputGate()
    with pytest.raises(IndexError):
        gate.remove_rule(0)


def test_remove_rule_returns_self_for_chaining():
    gate = InputGate(rules=[MaxInputLength(10)])
    returned = gate.remove_rule(0)
    assert returned is gate


def test_rules_returns_copy():
    r1 = MaxInputLength(10)
    gate = InputGate(rules=[r1])
    copy = gate.rules()
    copy.append(MaxInputLength(20))  # mutate the copy
    assert len(gate.rules()) == 1  # original unaffected


# ---------------------------------------------------------------------------
# GateResult.action_taken
# ---------------------------------------------------------------------------


def test_gate_result_action_taken_block_set_correctly():
    gate = InputGate(rules=[MaxInputLength(100)], action="block")
    result = gate.check("hi")
    assert result.action_taken == "block"


def test_gate_result_action_taken_warn_set_correctly():
    gate = InputGate(rules=[MaxInputLength(100)], action="warn")
    result = gate.check("hi")
    assert result.action_taken == "warn"


def test_gate_result_action_taken_pass_set_correctly():
    gate = InputGate(rules=[MaxInputLength(100)], action="pass")
    result = gate.check("hi")
    assert result.action_taken == "pass"
