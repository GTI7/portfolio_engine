"""Test setup for the custom_components/portfolio_engine pure-logic modules
(update_logic.py, sensor_mapping.py) without requiring the `homeassistant`
package to be installed.

`custom_components/portfolio_engine/__init__.py` imports `homeassistant.*`
at module level (correctly, for production use — HA is always present at
runtime for a real integration). Importing a submodule the normal way
(`import custom_components.portfolio_engine.update_logic`) would execute
that `__init__.py` first and fail here.

Fix: register stub entries in `sys.modules` for the two parent packages
before importing anything under them. Python's import machinery checks
`sys.modules` first and only executes a package's `__init__.py` if it isn't
already there — so the *real* `__init__.py` (and its `homeassistant`
imports) is never executed by these tests. The submodules under test
(`update_logic.py`, `sensor_mapping.py`) have no `homeassistant` imports of
their own, and their own relative imports (`.engine...`, `.providers...`,
`.repositories...`) resolve to real, HA-independent subpackages on disk.

This does NOT test coordinator.py, sensor.py, config_flow.py, __init__.py,
or diagnostics.py — those genuinely need `homeassistant` installed (or a
live HA instance) to exercise for real. See MILESTONE_2's validation notes
for how to do that.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _register_stub_package(name: str, path: Path) -> None:
    if name in sys.modules:
        return
    module = types.ModuleType(name)
    module.__path__ = [str(path)]  # marks it as a package for submodule imports
    sys.modules[name] = module


_register_stub_package("custom_components", ROOT / "custom_components")
_register_stub_package(
    "custom_components.portfolio_engine", ROOT / "custom_components" / "portfolio_engine"
)
