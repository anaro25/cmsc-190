from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
OUTPUTS_ROOT = PACKAGE_ROOT / "outputs"
STATIC_RANDOMIZED_DIR = OUTPUTS_ROOT / "static_randomized"
MAPF_RUNS_DIR = STATIC_RANDOMIZED_DIR
