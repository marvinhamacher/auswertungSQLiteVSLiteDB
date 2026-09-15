from __future__ import annotations

from dataclasses import dataclass
from math import isclose
from typing import Any, Mapping


@dataclass(frozen=True)
class CPUProfile:
    """Verified CPU profile for the benchmark environment.

    The Windows processor string alone is not unique enough. Therefore the
    profile also checks the observed core/thread count and reported maximum
    frequency. RAM is intentionally not part of CPU identification because it
    identifies the platform more than the CPU itself.
    """

    processor: str
    cores: int
    threads: int
    frequency_max_mhz: float
    name: str
    frequency_tolerance_mhz: float = 10.0


CPU_PROFILES: tuple[CPUProfile, ...] = (
    CPUProfile(
        processor="AMD64 Family 25 Model 97 Stepping 2, AuthenticAMD",
        cores=8,
        threads=16,
        frequency_max_mhz=3801.0,
        name="AMD Ryzen 7 7700",
    ),
    CPUProfile(
        processor="AMD64 Family 25 Model 97 Stepping 2, AuthenticAMD",
        cores=6,
        threads=12,
        frequency_max_mhz=3701.0,
        name="AMD Ryzen 5 7500F",
    ),
)


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _cpu_data(hardware: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(hardware, Mapping):
        return {}
    cpu = hardware.get("cpu", {})
    return cpu if isinstance(cpu, Mapping) else {}


def get_cpu_display_name(hardware: Mapping[str, Any] | None) -> str:
    """Return the verified CPU model name for a benchmark hardware object.

    Matching uses:
      1. Windows processor identification string
      2. physical/logical core count
      3. observed maximum CPU frequency

    If no verified profile matches, the original processor identification is
    returned instead of guessing a CPU model.
    """

    cpu = _cpu_data(hardware)
    processor = str(cpu.get("processor", "")).strip()
    cores = _number(cpu.get("cores"))
    threads = _number(cpu.get("threads"))

    frequency = cpu.get("frequency_mhz", {})
    if not isinstance(frequency, Mapping):
        frequency = {}
    frequency_max = _number(frequency.get("max"))

    for profile in CPU_PROFILES:
        if processor != profile.processor:
            continue
        if cores is None or int(cores) != profile.cores:
            continue
        if threads is None or int(threads) != profile.threads:
            continue
        if frequency_max is None:
            continue
        if isclose(
            frequency_max,
            profile.frequency_max_mhz,
            abs_tol=profile.frequency_tolerance_mhz,
        ):
            return profile.name

    return processor or "Unbekannte CPU"


# Backwards-compatible service-style wrapper for callers that prefer a class.
class HardwareService:
    @staticmethod
    def get_cpu_display_name(hardware: Mapping[str, Any] | None) -> str:
        return get_cpu_display_name(hardware)
