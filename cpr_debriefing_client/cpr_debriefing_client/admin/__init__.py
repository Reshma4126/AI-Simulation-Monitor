"""
admin/__init__.py — Admin package
==================================
Provides multi-admin authentication and feature-flag management.

Exports:
  AdminAuth          - login / session / user management
  FeatureFlags       - get / set feature toggles
  require_admin      - Flask route decorator
  require_super_admin- Flask route decorator (super_admin role only)
"""

from .auth import AdminAuth, require_admin, require_super_admin
from .feature_flags import FeatureFlags

__all__ = [
    "AdminAuth",
    "require_admin",
    "require_super_admin",
    "FeatureFlags",
]
