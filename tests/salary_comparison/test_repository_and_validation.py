import json
from copy import deepcopy

import pytest

from salary_comparison.repository import JsonRuleRepository, RuleNotFoundError
from salary_comparison.validators import RuleValidationError, validate_rule


def test_rule_validation_accepts_seed(malaysia_rule):
    normalized = validate_rule(malaysia_rule)
    assert normalized["currency"] == "MYR"
    assert normalized["tax_brackets"][0]["lower"] == 0
    assert normalized["tax_brackets_verified"] is True
    assert normalized["contribution_rule_verified"] is False


def test_rule_validation_rejects_noncontiguous(malaysia_rule):
    broken = deepcopy(malaysia_rule)
    broken["tax_brackets"][1]["lower"] = 6000
    with pytest.raises(RuleValidationError):
        validate_rule(broken)


def test_rule_validation_rejects_rate_above_one(malaysia_rule):
    broken = deepcopy(malaysia_rule)
    broken["contribution_rule"]["employee_rate"] = 1.1
    with pytest.raises(RuleValidationError):
        validate_rule(broken)


def test_repository_get_and_replace(data_dir, malaysia_rule):
    repo = JsonRuleRepository(data_dir / "tax_rules.json")
    assert repo.get_rule("malaysia", 2025, "resident")["currency"] == "MYR"
    updated = deepcopy(malaysia_rule)
    updated["notes"] = ["replacement"]
    repo.publish(updated)
    fetched = repo.get_rule("Malaysia", 2025, "Resident")
    assert fetched["notes"] == ["replacement"]
    assert len([
        r for r in repo.list_rules()
        if r["country"] == "Malaysia" and r["tax_year"] == 2025 and r["residency"] == "Resident"
    ]) == 1


def test_rule_validation_normalizes_contribution_profiles(malaysia_rule):
    normalized = validate_rule(malaysia_rule)
    assert normalized["default_contribution_profile"] == "malaysian_citizen"
    assert {profile["id"] for profile in normalized["contribution_profiles"]} >= {
        "permanent_resident", "employment_pass", "residence_pass_talent", "spousal_visa",
    }


def test_rule_validation_rejects_gapped_profile_periods(malaysia_rule):
    broken = deepcopy(malaysia_rule)
    profile = next(item for item in broken["contribution_profiles"] if item["id"] == "employment_pass")
    profile["periods"][1]["start_month"] = 11
    with pytest.raises(RuleValidationError, match="without gaps"):
        validate_rule(broken)


def test_repository_missing_rule(data_dir):
    repo = JsonRuleRepository(data_dir / "tax_rules.json")
    with pytest.raises(RuleNotFoundError):
        repo.get_rule("Japan", 2025, "Resident")

def test_rule_validation_rejects_brackets_after_open_end(malaysia_rule):
    broken = deepcopy(malaysia_rule)
    broken["tax_brackets"][0]["upper"] = None
    with pytest.raises(RuleValidationError):
        validate_rule(broken)

def test_bootstrap_adds_new_rules_without_overwriting_user_values(tmp_path):
    from salary_comparison.bootstrap import ensure_data_dir
    target = tmp_path / "persistent"
    ensure_data_dir(target)
    assert (target / "country_currency.json").exists()
    rule_path = target / "tax_rules.json"
    payload = json.loads(rule_path.read_text(encoding="utf-8"))
    payload["rules"] = [
        rule for rule in payload["rules"]
        if not (
            rule["country"] == "Malaysia"
            and rule["tax_year"] == 2025
            and rule["residency"] == "Non-Resident"
        )
    ]
    resident = next(
        rule for rule in payload["rules"]
        if rule["country"] == "Malaysia"
        and rule["tax_year"] == 2025
        and rule["residency"] == "Resident"
    )
    resident["tax_brackets"][0]["rate"] = 0.123
    resident.pop("contribution_profiles")
    resident.pop("default_contribution_profile")
    resident.pop("personal_reliefs_allowed")
    rule_path.write_text(json.dumps(payload), encoding="utf-8")

    ensure_data_dir(target)
    migrated = json.loads(rule_path.read_text(encoding="utf-8"))
    migrated_resident = next(
        rule for rule in migrated["rules"]
        if rule["country"] == "Malaysia"
        and rule["tax_year"] == 2025
        and rule["residency"] == "Resident"
    )
    assert migrated_resident["tax_brackets"][0]["rate"] == 0.123
    assert migrated_resident["contribution_profiles"]
    assert migrated_resident["personal_reliefs_allowed"] is True
    assert any(
        rule["country"] == "Malaysia"
        and rule["tax_year"] == 2025
        and rule["residency"] == "Non-Resident"
        for rule in migrated["rules"]
    )

    once = rule_path.read_text(encoding="utf-8")
    ensure_data_dir(target)
    assert rule_path.read_text(encoding="utf-8") == once


def test_bootstrap_repairs_matching_default_with_empty_profiles_idempotently(tmp_path):
    from salary_comparison.bootstrap import ensure_data_dir

    target = tmp_path / "persistent"
    ensure_data_dir(target)
    rule_path = target / "tax_rules.json"
    payload = json.loads(rule_path.read_text(encoding="utf-8"))
    resident = next(
        rule for rule in payload["rules"]
        if rule["country"] == "Malaysia"
        and rule["tax_year"] == 2025
        and rule["residency"] == "Resident"
    )
    resident["contribution_profiles"] = []
    rule_path.write_text(json.dumps(payload), encoding="utf-8")

    ensure_data_dir(target)
    repaired = json.loads(rule_path.read_text(encoding="utf-8"))
    repaired_resident = next(
        rule for rule in repaired["rules"]
        if rule["country"] == "Malaysia"
        and rule["tax_year"] == 2025
        and rule["residency"] == "Resident"
    )
    normalized = validate_rule(repaired_resident)
    assert normalized["contribution_profiles"]
    assert normalized["default_contribution_profile"] == "malaysian_citizen"

    once = rule_path.read_text(encoding="utf-8")
    ensure_data_dir(target)
    assert rule_path.read_text(encoding="utf-8") == once


def test_bootstrap_preserves_valid_explicit_empty_profile_list(tmp_path):
    from salary_comparison.bootstrap import ensure_data_dir

    target = tmp_path / "persistent"
    ensure_data_dir(target)
    rule_path = target / "tax_rules.json"
    payload = json.loads(rule_path.read_text(encoding="utf-8"))
    resident = next(
        rule for rule in payload["rules"]
        if rule["country"] == "Malaysia"
        and rule["tax_year"] == 2025
        and rule["residency"] == "Resident"
    )
    resident["contribution_profiles"] = []
    resident.pop("default_contribution_profile", None)
    rule_path.write_text(json.dumps(payload), encoding="utf-8")
    before = rule_path.read_text(encoding="utf-8")

    ensure_data_dir(target)

    after = rule_path.read_text(encoding="utf-8")
    assert after == before
    stored = json.loads(after)["rules"]
    preserved = next(
        rule for rule in stored
        if rule["country"] == "Malaysia"
        and rule["tax_year"] == 2025
        and rule["residency"] == "Resident"
    )
    assert validate_rule(preserved)["contribution_profiles"] == []


def test_bootstrap_does_not_replace_empty_custom_profile_pair(tmp_path):
    from salary_comparison.bootstrap import ensure_data_dir

    target = tmp_path / "persistent"
    ensure_data_dir(target)
    rule_path = target / "tax_rules.json"
    payload = json.loads(rule_path.read_text(encoding="utf-8"))
    resident = next(
        rule for rule in payload["rules"]
        if rule["country"] == "Malaysia"
        and rule["tax_year"] == 2025
        and rule["residency"] == "Resident"
    )
    resident["default_contribution_profile"] = "custom_profile"
    resident["contribution_profiles"] = []
    rule_path.write_text(json.dumps(payload), encoding="utf-8")
    before = rule_path.read_text(encoding="utf-8")

    ensure_data_dir(target)

    assert rule_path.read_text(encoding="utf-8") == before


def test_bootstrap_does_not_replace_malformed_user_rule_file(tmp_path):
    from salary_comparison.bootstrap import ensure_data_dir
    target = tmp_path / "persistent"
    target.mkdir()
    rule_path = target / "tax_rules.json"
    rule_path.write_text('{"rules": [{"custom": true}]}', encoding="utf-8")

    ensure_data_dir(target)

    assert rule_path.read_text(encoding="utf-8") == '{"rules": [{"custom": true}]}'
