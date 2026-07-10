#!/usr/bin/env bash
# One-time setup for running tests_ha/ against the real Home Assistant
# test harness. Separate from requirements-test.txt on purpose (see
# MILESTONE_2_5.md) — this pulls in the full `homeassistant` package, which
# the rest of the project (tests/, tests_integration/) doesn't need.
#
# Usage:
#   ./scripts/setup_ha_test_env.sh
#   .ha_test_venv/bin/python -m pytest tests_ha/ -v
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${REPO_ROOT}/.ha_test_venv"

python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install --upgrade pip -q
"${VENV_DIR}/bin/pip" install -r "${REPO_ROOT}/requirements-ha-test.txt" -q

# HA's custom-integration test harness discovers integrations via a fixed
# testing_config/custom_components/ directory bundled inside the harness
# package itself (see MILESTONE_2_5.md's "How this works" section for why).
# Symlink this repo's integration into it once.
HARNESS_TESTING_CONFIG="$("${VENV_DIR}/bin/python" -c \
  "import pytest_homeassistant_custom_component, os; \
   print(os.path.join(os.path.dirname(pytest_homeassistant_custom_component.__file__), \
   'testing_config', 'custom_components'))")"

ln -sf "${REPO_ROOT}/custom_components/portfolio_engine" \
  "${HARNESS_TESTING_CONFIG}/portfolio_engine"

echo "Done. Run tests with:"
echo "  ${VENV_DIR}/bin/python -m pytest tests_ha/ -v"
