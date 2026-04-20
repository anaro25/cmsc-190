import shutil
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
OUTPUTS_ROOT = PACKAGE_ROOT / "outputs"
RAW_MAPF_DATA_ROOT = PACKAGE_ROOT / "raw_mapf_data"

STATIC_ARTIFICIAL_DIR = OUTPUTS_ROOT / "static_artificial"
DYNAMIC_PORT_DIR = OUTPUTS_ROOT / "dynamic_port"

for _path in [OUTPUTS_ROOT, RAW_MAPF_DATA_ROOT, STATIC_ARTIFICIAL_DIR, DYNAMIC_PORT_DIR]:
    _path.mkdir(parents=True, exist_ok=True)


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
