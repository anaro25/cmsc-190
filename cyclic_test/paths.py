from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
OUTPUTS_ROOT = PACKAGE_ROOT / "outputs"
CLASSICAL_LOGS_DIR = OUTPUTS_ROOT / "classical_logs"
CYCLIC_LOGS_DIR = OUTPUTS_ROOT / "cyclic_logs"
MAPF_RUNS_DIR = OUTPUTS_ROOT / "mapf_runs"
