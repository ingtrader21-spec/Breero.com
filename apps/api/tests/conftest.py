"""Shared test-process defaults.

Tests must be runnable from a fresh checkout without relying on an operator's
shell environment. Production/staging settings remain explicit; only the test
process receives the safe test environment default.
"""

from __future__ import annotations

import os

os.environ.setdefault("APP_ENV", "test")
