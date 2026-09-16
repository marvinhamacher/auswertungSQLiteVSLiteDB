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
    # AMD Ryzen 7000 / Zen 4
    CPUProfile(
        processor="AMD64 Family 25 Model 97 Stepping 2, AuthenticAMD",
        cores=8,
        threads=16,
        frequency_max_mhz=3801.0,
        name="AMD Ryzen 7 7700",
    ),
    CPUProfile(
        processor="AMD64 Family 25 Model 97 Stepping 2, AuthenticAMD",
        cores=8,
        threads=16,
        frequency_max_mhz=4201.0,
        name="AMD Ryzen 7 7800X3D",
    ),
    CPUProfile(
        processor="AMD64 Family 25 Model 97 Stepping 2, AuthenticAMD",
        cores=6,
        threads=12,
        frequency_max_mhz=3701.0,
        name="AMD Ryzen 5 7500F",
    ),
    CPUProfile(
        processor="AMD64 Family 25 Model 97 Stepping 2, AuthenticAMD",
        cores=6,
        threads=12,
        frequency_max_mhz=3801.0,
        name="AMD Ryzen 5 7600",
    ),

    CPUProfile(
        processor="AMD64 Family 25 Model 33 Stepping 2, AuthenticAMD",
        cores=6,
        threads=12,
        frequency_max_mhz=3701.0,
        name="AMD Ryzen 5 5600X",
    ),

    # AMD Ryzen 3000
    CPUProfile(
        processor="AMD64 Family 23 Model 113 Stepping 0, AuthenticAMD",
        cores=6,
        threads=12,
        frequency_max_mhz=3593.0,
        name="AMD Ryzen 5 3600",
    ),

    # AMD Ryzen 2000
    CPUProfile(
        processor="AMD64 Family 23 Model 8 Stepping 2, AuthenticAMD",
        cores=8,
        threads=16,
        frequency_max_mhz=3700.0,
        name="AMD Ryzen 7 2700X",
    ),

    # AMD mobile
    CPUProfile(
        processor="AMD64 Family 23 Model 104 Stepping 1, AuthenticAMD",
        cores=6,
        threads=12,
        frequency_max_mhz=2100.0,
        name="AMD Ryzen 5 5500U",
    ),

    # AMD Ryzen 9000 / Zen 5
    CPUProfile(
        processor="AMD64 Family 26 Model 68 Stepping 0, AuthenticAMD",
        cores=16,
        threads=32,
        frequency_max_mhz=4300.0,
        name="AMD Ryzen 9 9950X3D",
    ),

    # Intel 14th Gen
    CPUProfile(
        processor="Intel64 Family 6 Model 183 Stepping 1, GenuineIntel",
        cores=20,
        threads=28,
        frequency_max_mhz=3400.0,
        name="Intel Core i7-14700K",
    ),

    # Intel 13th Gen mobile
    CPUProfile(
        processor="Intel64 Family 6 Model 186 Stepping 3, GenuineIntel",
        cores=10,
        threads=12,
        frequency_max_mhz=1300.0,
        name="Intel Core i5-1335U",
    ),

    # Intel 8th/9th Gen
    CPUProfile(
        processor="Intel64 Family 6 Model 158 Stepping 10, GenuineIntel",
        cores=6,
        threads=12,
        frequency_max_mhz=2001.0,
        name="Intel Core i7-8700",
    ),
    CPUProfile(
        processor="Intel64 Family 6 Model 158 Stepping 10, GenuineIntel",
        cores=6,
        threads=6,
        frequency_max_mhz=2904.0,
        name="Intel Core i5-9400F",
    ),

    # Intel mobile
    CPUProfile(
        processor="Intel64 Family 6 Model 142 Stepping 10, GenuineIntel",
        cores=4,
        threads=8,
        frequency_max_mhz=1896.0,
        name="Intel Core i7-8559U",
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
