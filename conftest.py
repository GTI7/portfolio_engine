import sys
from pathlib import Path

# Allow `import engine`, `import repositories`, `import providers` from tests
# without packaging/installing this as a distributable package yet — fine
# for Milestone 1; a proper pyproject.toml / setup.cfg is a Milestone 2
# concern once this moves inside custom_components/.
sys.path.insert(0, str(Path(__file__).parent))
