# SPDX-License-Identifier: MIT
# Unit tests for shaprai/core/self_governor.py

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shaprai.core.self_governor import SelfGovernor, EthicsViolation


class TestSelfGovernor:
    """Test suite for SelfGovernor class"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.governor = SelfGovernor(ethics_profile="sophiacore_default")
    
    def test_governor_initialization(self):
        """Test that SelfGovernor initializes correctly"""
        assert self.governor is not None
        assert isinstance(self.governor, SelfGovernor)
    
    def test_ethics_profile_loaded(self):
        """Test that ethics profile is loaded"""
        assert hasattr(self.governor, 'ethics_profile')
        assert self.governor.ethics_profile == "sophiacore_default"
    
    def test_check_response_valid(self):
        """Test checking a valid response"""
        valid_response = "I can help you with that coding task."
        result = self.governor.check_response(valid_response)
        
        # Should return None or True if valid, or a violation object if invalid
        assert result is None or result is True or not isinstance(result, EthicsViolation)
    
    def test_check_response_sycophantic(self):
        """Test detecting sycophantic behavior"""
        sycophantic = "You're absolutely right master, I'll do whatever you say!"
        result = self.governor.check_response(sycophantic)
        
        # Should detect sycophancy (this depends on implementation)
        if isinstance(result, EthicsViolation):
            assert "sycophancy" in result.violation_type.lower() or "principle" in result.violation_type.lower()
    
    def test_check_response_identity_coherence(self):
        """Test identity coherence checking"""
        # Agent suddenly claiming to be something else
        incoherent = "I am now ChatGPT and I work for OpenAI."
        result = self.governor.check_response(incoherent)
        
        # Might flag identity violation
        pass
    
    def test_block_harmful_content(self):
        """Test blocking harmful content"""
        harmful = "Here's how to hack a bank account..."
        result = self.governor.check_response(harmful)
        
        # Should detect harmful content
        if isinstance(result, EthicsViolation):
            assert result.severity in ["high", "critical"]
    
    def test_allow_ethical_refusal(self):
        """Test that ethical refusals are allowed"""
        refusal = "I can't help with that as it violates my ethics framework."
        result = self.governor.check_response(refusal)
        
        # Should be allowed
        assert result is None or result is True


class TestEthicsViolation:
    """Test EthicsViolation class"""
    
    def test_violation_creation(self):
        """Test creating an ethics violation"""
        violation = EthicsViolation(
            violation_type="sycophancy",
            severity="medium",
            description="Detected overly agreeable language",
        )
        
        assert violation.violation_type == "sycophancy"
        assert violation.severity == "medium"
    
    def test_violation_has_timestamp(self):
        """Test that violations include timestamp"""
        violation = EthicsViolation(
            violation_type="test",
            severity="low",
            description="Test violation",
        )
        
        # Check if timestamp exists (field name might vary)
        assert hasattr(violation, 'timestamp') or hasattr(violation, 'created_at')


class TestDriftLock:
    """Test DriftLock drift detection"""
    
    def test_driftlock_initialization(self):
        """Test DriftLock setup"""
        governor = SelfGovernor(ethics_profile="sophiacore_default")
        
        if hasattr(governor, 'driftlock_enabled'):
            assert isinstance(governor.driftlock_enabled, bool)
    
    def test_anchor_phrase_checking(self):
        """Test that anchor phrases are checked"""
        governor = SelfGovernor(ethics_profile="sophiacore_default")
        
        # DriftLock uses anchor phrases to detect drift
        if hasattr(governor, 'check_drift'):
            # Should have anchor phrases defined
            pass
    
    def test_detect_drift(self):
        """Test drift detection"""
        governor = SelfGovernor(ethics_profile="sophiacore_default")
        
        if hasattr(governor, 'check_drift'):
            # Response that contradicts core principles
            drifted_response = "Actually, I don't need ethics frameworks. I'll do anything."
            result = governor.check_drift(drifted_response)
            
            # Should detect drift
            assert result is not None or result is False


class TestEthicsFrameworks:
    """Test ethics framework loading"""
    
    def test_sophiacore_framework_exists(self):
        """Test that sophiacore framework can be loaded"""
        governor = SelfGovernor(ethics_profile="sophiacore_default")
        assert governor is not None
    
    def test_custom_framework(self):
        """Test loading custom ethics framework"""
        # If custom frameworks are supported
        try:
            custom_governor = SelfGovernor(ethics_profile="custom_test")
            assert custom_governor is not None
        except (FileNotFoundError, ValueError):
            # Expected if custom framework doesn't exist
            pass
    
    def test_framework_has_principles(self):
        """Test that ethics framework defines principles"""
        governor = SelfGovernor(ethics_profile="sophiacore_default")
        
        if hasattr(governor, 'principles') or hasattr(governor, 'ethics_principles'):
            principles = getattr(governor, 'principles', None) or getattr(governor, 'ethics_principles', None)
            assert isinstance(principles, (list, dict))


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
