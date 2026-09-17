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
    ram_generation: str
    frequency_tolerance_mhz: float = 10.0


CPU_PROFILES: tuple[CPUProfile, ...] = (
    # AMD Ryzen 9000 / Zen 5
    CPUProfile(
        "AMD64 Family 26 Model 68 Stepping 0, AuthenticAMD",
        16, 32, 4300.0, "AMD Ryzen 9 9950X", "DDR5",
    ),

    # AMD Ryzen 7000 / Zen 4
    CPUProfile(
        "AMD64 Family 25 Model 97 Stepping 2, AuthenticAMD",
        8, 16, 4201.0, "AMD Ryzen 7 7800X3D", "DDR5",
    ),
    CPUProfile(
        "AMD64 Family 25 Model 97 Stepping 2, AuthenticAMD",
        8, 16, 3801.0, "AMD Ryzen 7 7700", "DDR5",
    ),
    CPUProfile(
        "AMD64 Family 25 Model 97 Stepping 2, AuthenticAMD",
        6, 12, 3701.0, "AMD Ryzen 5 7500F", "DDR5",
    ),
    CPUProfile(
        "AMD64 Family 25 Model 97 Stepping 2, AuthenticAMD",
        6, 12, 3801.0, "AMD Ryzen 5 7600", "DDR5",
    ),

    # AMD Ryzen 5000 / Zen 3
    CPUProfile(
        "AMD64 Family 25 Model 33 Stepping 2, AuthenticAMD",
        6, 12, 3701.0, "AMD Ryzen 5 5600X", "DDR4",
    ),

    # AMD Ryzen 3000 / Zen 2
    CPUProfile(
        "AMD64 Family 23 Model 113 Stepping 0, AuthenticAMD",
        6, 12, 3593.0, "AMD Ryzen 5 3600", "DDR4",
    ),

    # AMD Ryzen 2000 / Zen+
    CPUProfile(
        "AMD64 Family 23 Model 8 Stepping 2, AuthenticAMD",
        8, 16, 3700.0, "AMD Ryzen 7 2700X", "DDR4",
    ),

    # AMD mobile
    CPUProfile(
        "AMD64 Family 23 Model 104 Stepping 1, AuthenticAMD",
        6, 12, 2100.0, "AMD Ryzen 5 5500U", "DDR4",
    ),

    # Intel 14th Gen
    CPUProfile(
        "Intel64 Family 6 Model 183 Stepping 1, GenuineIntel",
        20, 28, 3400.0, "Intel Core i7-14700K", "DDR5",
    ),

    # Intel 13th Gen mobile
    CPUProfile(
        "Intel64 Family 6 Model 186 Stepping 3, GenuineIntel",
        10, 12, 1300.0, "Intel Core i5-1335U", "DDR4",
    ),

    # Intel 8th/9th Gen
    CPUProfile(
        "Intel64 Family 6 Model 158 Stepping 10, GenuineIntel",
        6, 12, 2001.0, "Intel Core i7-8700", "DDR4",
    ),
    CPUProfile(
        "Intel64 Family 6 Model 158 Stepping 10, GenuineIntel",
        6, 6, 2904.0, "Intel Core i5-9400F", "DDR4",
    ),

    # Intel mobile
    CPUProfile(
        "Intel64 Family 6 Model 142 Stepping 10, GenuineIntel",
        4, 8, 1896.0, "Intel Core i5-8350U", "DDR4",
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


def _ram_data(hardware: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(hardware, Mapping):
        return {}
    ram = hardware.get("ram", {})
    return ram if isinstance(ram, Mapping) else {}


def _matching_cpu_profile(hardware: Mapping[str, Any] | None) -> CPUProfile | None:
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
            return profile

    return None


def get_ram_generation(hardware: Mapping[str, Any] | None) -> str:
    """Return the RAM generation for a benchmark hardware object.

    Known CPUs use the RAM generation stored in their verified CPU profile.
    This avoids relying on the RAM clock alone, since DDR4 and DDR5 can
    overlap in clock speeds. For an unknown CPU, the stored RAM frequency
    is used as a fallback heuristic.
    """

    profile = _matching_cpu_profile(hardware)
    if profile is not None:
        return profile.ram_generation

    ram = _ram_data(hardware)
    ram_frequency = _number(ram.get("frequency_mhz"))
    if ram_frequency is None:
        return "Unbekannter RAM"

    return "DDR5" if ram_frequency >= 4800 else "DDR4"


def get_cpu_display_name(hardware: Mapping[str, Any] | None) -> str:
    """Return the verified CPU model name for a benchmark hardware object."""

    profile = _matching_cpu_profile(hardware)
    if profile is not None:
        return profile.name

    cpu = _cpu_data(hardware)
    processor = str(cpu.get("processor", "")).strip()
    return processor or "Unbekannte CPU"


# Backwards-compatible service-style wrapper for callers that prefer a class.
class HardwareService:
    @staticmethod
    def get_cpu_display_name(hardware: Mapping[str, Any] | None) -> str:
        return get_cpu_display_name(hardware)

    @staticmethod
    def get_ram_generation(hardware: Mapping[str, Any] | None) -> str:
        return get_ram_generation(hardware)
