from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
OUTPUTS_ROOT = PACKAGE_ROOT / "outputs"

STATIC_ARTIFICIAL_DIR = OUTPUTS_ROOT / "static_artificial"
DYNAMIC_PORT_DIR = OUTPUTS_ROOT / "dynamic_port"


def get_context_output_dir(context_name):
    output_dir = OUTPUTS_ROOT / context_name
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir
