"""Shared fixtures for the SpecGuard test suite."""

import pytest

from specguard.data.cva6_requirements import get_all_requirements


@pytest.fixture(scope="session")
def cva6_requirements():
    """Return the full CVA6 dataset (64 requirements). Session-scoped for speed."""
    return get_all_requirements()
