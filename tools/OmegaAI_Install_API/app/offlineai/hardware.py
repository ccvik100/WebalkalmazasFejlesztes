"""Helyi CPU/GPU képességvizsgálat. Semmilyen hálózati vagy modellletöltést nem végez."""
from __future__ import annotations
import importlib.util
import subprocess
from .core import config


def hardware_report() -> dict:
    result = {"requested_device": config().get("device", "cpu"), "cuda_available": False,
              "ctranslate2_cuda": False, "torch_cuda": False, "gpu_name": None,
              "whisper_device": "cpu", "pyannote_device": "cpu", "warnings": []}
    if importlib.util.find_spec("torch") is not None:
        try:
            import torch
            result["torch_cuda"] = bool(torch.cuda.is_available())
            if result["torch_cuda"]:
                result["gpu_name"] = torch.cuda.get_device_name(0)
        except Exception as exc:
            result["warnings"].append("PyTorch GPU-vizsgálat sikertelen: " + str(exc)[:140])
    if importlib.util.find_spec("ctranslate2") is not None:
        try:
            import ctranslate2
            result["ctranslate2_cuda"] = bool(ctranslate2.get_supported_compute_types("cuda"))
        except Exception as exc:
            result["warnings"].append("CTranslate2 CUDA nem elérhető: " + str(exc)[:140])
    result["cuda_available"] = result["torch_cuda"] and result["ctranslate2_cuda"]
    requested = config().get("device", "cpu")
    if requested not in ("auto", "cpu", "cuda"):
        raise ValueError("device csak cpu, cuda vagy auto lehet.")
    if requested == "cuda" and not result["cuda_available"]:
        raise RuntimeError("GPU mód kérve, de CUDA nem működik a PyTorch és CTranslate2 alatt egyaránt. Állítsd device=auto vagy cpu értékre; részletek: /v1/hardware.")
    if requested == "auto" and not result["cuda_available"]:
        result["warnings"].append("CUDA nem használható mindkét modellhez; CPU-re váltunk (nincs néma GPU-állítás).")
    if requested == "cuda" or (requested == "auto" and result["cuda_available"]):
        result["whisper_device"] = "cuda"
        result["pyannote_device"] = "cuda"
    result["whisper_compute_type"] = ("float16" if result["whisper_device"] == "cuda"
                                      and config().get("compute_type") in ("auto", "int8")
                                      else "int8" if config().get("compute_type") == "auto" else config().get("compute_type", "int8"))
    return result
