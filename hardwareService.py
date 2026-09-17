from __future__ import annotations

from dataclasses import dataclass
from math import isclose
from typing import Any, Mapping


@dataclass(frozen=True)
class CPUProfile:

    processor: str
    cores: int
    threads: int
    frequency_max_mhz: float
    name: str
    frequency_tolerance_mhz: float = 10.0


# Family/Model alone is deliberately not used because several CPUs share the
# same Windows processor identification string. Core/thread count and the
# observed maximum frequency distinguish the profiles in this benchmark set.
CPU_PROFILES: tuple[CPUProfile, ...] = (
    # AMD Ryzen 9000 / Zen 5
    CPUProfile(
        "AMD64 Family 26 Model 68 Stepping 0, AuthenticAMD",
        16, 32, 4300.0, "AMD Ryzen 9 9950X",
    ),

    # AMD Ryzen 7000 / Zen 4
    CPUProfile(
        "AMD64 Family 25 Model 97 Stepping 2, AuthenticAMD",
        8, 16, 4201.0, "AMD Ryzen 7 7800X3D",
    ),
    CPUProfile(
        "AMD64 Family 25 Model 97 Stepping 2, AuthenticAMD",
        8, 16, 3801.0, "AMD Ryzen 7 7700",
    ),
    CPUProfile(
        "AMD64 Family 25 Model 97 Stepping 2, AuthenticAMD",
        6, 12, 3701.0, "AMD Ryzen 5 7500F",
    ),
    CPUProfile(
        "AMD64 Family 25 Model 97 Stepping 2, AuthenticAMD",
        6, 12, 3801.0, "AMD Ryzen 5 7600",
    ),

    # AMD Ryzen 5000 / Zen 3
    CPUProfile(
        "AMD64 Family 25 Model 33 Stepping 2, AuthenticAMD",
        6, 12, 3701.0, "AMD Ryzen 5 5600X",
    ),

    # AMD Ryzen 3000 / Zen 2
    CPUProfile(
        "AMD64 Family 23 Model 113 Stepping 0, AuthenticAMD",
        6, 12, 3593.0, "AMD Ryzen 5 3600",
    ),

    # AMD Ryzen 2000 / Zen+
    CPUProfile(
        "AMD64 Family 23 Model 8 Stepping 2, AuthenticAMD",
        8, 16, 3700.0, "AMD Ryzen 7 2700X",
    ),

    # AMD mobile
    CPUProfile(
        "AMD64 Family 23 Model 104 Stepping 1, AuthenticAMD",
        6, 12, 2100.0, "AMD Ryzen 5 5500U",
    ),

    # Intel 14th Gen
    CPUProfile(
        "Intel64 Family 6 Model 183 Stepping 1, GenuineIntel",
        20, 28, 3400.0, "Intel Core i7-14700K",
    ),

    # Intel 13th Gen mobile
    CPUProfile(
        "Intel64 Family 6 Model 186 Stepping 3, GenuineIntel",
        10, 12, 1300.0, "Intel Core i5-1335U",
    ),

    # Intel 8th/9th Gen
    CPUProfile(
        "Intel64 Family 6 Model 158 Stepping 10, GenuineIntel",
        6, 12, 2001.0, "Intel Core i7-8700",
    ),
    CPUProfile(
        "Intel64 Family 6 Model 158 Stepping 10, GenuineIntel",
        6, 6, 2904.0, "Intel Core i5-9400F",
    ),

    # Intel mobile
    CPUProfile(
        "Intel64 Family 6 Model 142 Stepping 10, GenuineIntel",
        4, 8, 1896.0, "Intel Core i7-8559U",
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


class HardwareService:
    @staticmethod
    def get_cpu_display_name(hardware: Mapping[str, Any] | None) -> str:
        return get_cpu_display_name(hardware)
