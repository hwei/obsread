"""Reject tags that disagree with the installed distribution version."""

import sys
from importlib.metadata import version

expected = f"v{version('obsread')}"
if len(sys.argv) != 2 or sys.argv[1] != expected:
    raise SystemExit(f"Release tag must be {expected}")
print(f"Verified {expected}")
