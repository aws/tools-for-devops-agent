"""
Unit tests for the human-in-the-loop collection approval gate (M1/M2) and the
E4/E5 hardening helpers. These cover the pure-logic paths that do not require
AWS calls (bypass, disabled, fail-closed, log-key scoping, regex safety).
"""
import os
import sys
import json
import pytest

# Set required env vars before importing the module
os.environ.setdefault('LOGS_BUCKET_NAME', 'test-bucket')
os.environ.setdefault('SSM_AUTOMATION_ROLE_ARN', 'arn:aws:iam::123456789012:role/test')
os.environ.setdefault('AWS_REGION', 'us-east-1')
os.environ.setdefault('ALLOWED_REGIONS', 'us-east-1,us-west-2')
os.environ.setdefault('SOP_BUCKET_NAME', 'test-sop-bucket')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'lambda'))

mod = __import__('ssm-automation-enhanced')

VALID_KEY = 'eks_i-0123456789abcdef0_exec123/var/log/kubelet.log'
INSTANCE = 'i-0123456789abcdef0'
OTHER_INSTANCE = 'i-0fedcba9876543210'


class TestApprovalGate:
    def test_bypass_flag_skips_approval(self):
        """Server-side _approval_bypass short-circuits the gate (used by batch)."""
        result = mod.enforce_collection_approval(
            'collect', INSTANCE, 'us-east-1', {'_approval_bypass': True}
        )
        assert result is None

    def test_disabled_returns_none(self, monkeypatch):
        """When approval is disabled, the gate lets the call proceed."""
        monkeypatch.setattr(mod, 'REQUIRE_COLLECTION_APPROVAL', False)
        result = mod.enforce_collection_approval('collect', INSTANCE, 'us-east-1', {})
        assert result is None

    def test_required_but_unconfigured_fails_closed(self, monkeypatch):
        """Approval required but no table configured -> 503, never runs unapproved."""
        monkeypatch.setattr(mod, 'REQUIRE_COLLECTION_APPROVAL', True)
        monkeypatch.setattr(mod, 'APPROVAL_TABLE_NAME', '')
        result = mod.enforce_collection_approval('collect', INSTANCE, 'us-east-1', {})
        assert result is not None
        assert result['statusCode'] == 503


class TestLogKeyScoping:
    def test_valid_key_no_instance(self):
        assert mod.validate_log_key(VALID_KEY) is None

    def test_valid_key_matching_instance(self):
        assert mod.validate_log_key(VALID_KEY, expected_instance_id=INSTANCE) is None

    def test_key_for_other_instance_rejected(self):
        result = mod.validate_log_key(VALID_KEY, expected_instance_id=OTHER_INSTANCE)
        assert result is not None and result['statusCode'] == 403

    def test_path_traversal_rejected(self):
        result = mod.validate_log_key('eks_i-0123456789abcdef0_exec/../../etc/passwd')
        assert result is not None and result['statusCode'] == 400

    def test_non_bundle_key_rejected(self):
        result = mod.validate_log_key('some/random/object.json')
        assert result is not None and result['statusCode'] == 400


class TestRegexSafety:
    @pytest.mark.parametrize('pattern', ['(a+)+', '(a*)+', r'(\d+){3,}'])
    def test_flags_catastrophic(self, pattern):
        assert mod.is_catastrophic_regex(pattern) is True

    @pytest.mark.parametrize('pattern', ['ERROR|WARN', 'kubelet.*failed', r'\bOOMKilled\b'])
    def test_allows_normal(self, pattern):
        assert mod.is_catastrophic_regex(pattern) is False
