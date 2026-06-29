import shutil
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
OUTPUTS_ROOT = PACKAGE_ROOT / "outputs"
OUTPUTS_REF_COMPARISON_ROOT = PACKAGE_ROOT / "outputs_ref_comparison"
RAW_MAPF_DATA_ROOT = OUTPUTS_ROOT / "raw_mapf_files"
RAW_REF_COMPARISON_DATA_ROOT = OUTPUTS_REF_COMPARISON_ROOT / "raw_mapf_files"
LEGACY_RAW_MAPF_DATA_ROOTS = [
    PACKAGE_ROOT / "raw_mapf_data",
    PACKAGE_ROOT / "raw_mapf_files",
]

STATIC_ARTIFICIAL_DIR = OUTPUTS_ROOT / "static_artificial"
DYNAMIC_PORT_DIR = OUTPUTS_ROOT / "dynamic_port"


def get_context_output_dir(context_name):
    output_dir = OUTPUTS_ROOT / context_name
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def clear_output_dir(output_dir):
    output_dir = Path(output_dir)
    if output_dir.exists():
        for child in output_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    output_dir.mkdir(parents=True, exist_ok=True)
