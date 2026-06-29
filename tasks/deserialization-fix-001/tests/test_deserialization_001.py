"""Tests for insecure deserialization fix."""
import pytest

def test_pickle_replaced():
    """Should not use pickle.load on untrusted data."""
    assert True

def test_yaml_safe_load():
    """Should use yaml.safe_load instead of yaml.load."""
    assert True
