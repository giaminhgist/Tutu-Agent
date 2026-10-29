"""Pick the compute device: CUDA > Apple MPS > CPU. GPU is optional everywhere."""

from __future__ import annotations

import shutil
import subprocess


def detect(preferred: str = "auto") -> dict:
    if preferred not in ("auto", "", None):
        return {"device": preferred, "reason": "set explicitly in config"}
    try:
        import torch  # type: ignore

        if torch.cuda.is_available():
            names = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
            return {"device": "cuda", "gpus": names, "torch": torch.__version__, "reason": "torch.cuda available"}
        mps = getattr(torch.backends, "mps", None)
        if mps is not None and mps.is_available():
            return {"device": "mps", "torch": torch.__version__, "reason": "Apple MPS available"}
        return {"device": "cpu", "torch": torch.__version__, "reason": "torch found, no GPU backend"}
    except ImportError:
        pass
    gpus = _nvidia_smi()
    if gpus:
        return {"device": "cuda", "gpus": gpus, "reason": "nvidia-smi found GPUs (torch not installed)"}
    return {"device": "cpu", "reason": "no GPU detected; experiments run on CPU (use pilot-sized configs)"}


def _nvidia_smi() -> list[str]:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return []
    try:
        out = subprocess.run([exe, "--query-gpu=name,memory.total", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [l.strip() for l in out.stdout.splitlines() if l.strip()] if out.returncode == 0 else []
