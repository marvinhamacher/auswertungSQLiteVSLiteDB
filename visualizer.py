from __future__ import annotations

import argparse
import json
import math
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.colors import hsv_to_rgb

from hardwareService import get_cpu_display_name


DB_LABELS = {
    "sqlite": "SQLite",
    "litedb": "LiteDB",
}

DBS = ["sqlite", "litedb"]

OPS = [
    "insert",
    "select",
    "update",
    "transaction",
    "delete",
]

METRICS = {
    "exec_time": "Ausführungszeit",
    "tps": "TPS",
    "queryrate": "Query Rate",
    "latency_avg": "Latenz Ø",
    "latency_min": "Latenz min",
    "latency_max": "Latenz max",
}

CATEGORIES = {
    "lowend": "Low-End",
    "midrange": "Mid-Range",
    "highend": "High-End",
    "unknown": "Unbekannt",
}

COLOR_MODES = {
    "hardware": "Hardware",
    "akribisch": "Akribisch",
    "datenbank": "Datenbank (SQLite / LiteDB)",
}

# Fixed database colors: these never depend on hardware, test or result order.
DB_COLORS = {
    "sqlite": "#4C78A8",
    "litedb": "#F58518",
}

CUSTOM_CPU_CATEGORY_MAP = {}

# Explicit, editable hardware tiers. RAM capacity must not turn an old CPU
# into "High-End" merely because it has a lot of memory.
CPU_HARDWARE_LEVELS = {
    "AMD Ryzen 9 9950X": "highend",
    "AMD Ryzen 7 7800X3D": "highend",
    "AMD Ryzen 7 7700": "highend",
    "AMD Ryzen 7 7600X": "highend",
    "Intel Core i7-14700K": "highend",

    "AMD Ryzen 5 7600": "midrange",
    "AMD Ryzen 5 7500F": "midrange",
    "AMD Ryzen 5 5600X": "midrange",
    "AMD Ryzen 5 3600": "midrange",
    "AMD Ryzen 7 2700X": "midrange",
    "Intel Core i7-8700": "midrange",
    "Intel Core i5-9400F": "midrange",

    "AMD Ryzen 5 5500U": "lowend",
    "Intel Core i5-1335U": "lowend",
    "Intel Core i7-8559U": "lowend",
}

# A compact base palette is used first. If more systems are loaded, colors
# continue deterministically through HSV instead of failing or repeating too
# early.
BASE_COLORS = [
    "#4C78A8", "#F58518", "#E45756", "#72B7B2", "#54A24B",
    "#EECA3B", "#B279A2", "#FF9DA6", "#9D755D", "#BAB0AC",
    "#5F9ED1", "#E17C05", "#D94F4F", "#5FAFA9", "#4B9346",
    "#C7A82C", "#8F6594", "#E27C87", "#87644F", "#99918E",
]


def num(value, default=math.nan):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def score_hardware(hw):
    cpu = hw.get("cpu", {})
    ram = hw.get("ram", {})

    return (
        num(cpu.get("cores"), 0) * 30
        + num(cpu.get("threads"), 0) * 15
        + num((cpu.get("frequency_mhz") or {}).get("max"), 0) / 100 * 5
        + num(ram.get("size_gb"), 0) * 2
        + num(ram.get("frequency_mhz"), 0) / 1000 * 10
    )


def category(hw):
    raw = hw.get("cpu", {}).get("processor", "")

    if raw in CUSTOM_CPU_CATEGORY_MAP:
        return CUSTOM_CPU_CATEGORY_MAP[raw]

    verified_name = get_cpu_display_name(hw)
    if verified_name in CPU_HARDWARE_LEVELS:
        return CPU_HARDWARE_LEVELS[verified_name]

    # Fallback for CPUs not yet added to CPU_HARDWARE_LEVELS.
    score = score_hardware(hw)
    if score <= 349:
        return "lowend"
    if score <= 649:
        return "midrange"
    return "highend"


def cpu_name(hw):
    return get_cpu_display_name(hw)


def test_code(data):
    """Read an explicitly stored test code from the JSON, if present."""
    keys = [
        "test_code", "testCode", "test_id", "testId",
        "testkürzel", "testkuerzel", "code",
    ]

    for key in keys:
        if data.get(key) not in (None, ""):
            return str(data[key])

    metadata = data.get("metadata", {})
    if isinstance(metadata, dict):
        for key in keys:
            if metadata.get(key) not in (None, ""):
                return str(metadata[key])

    return ""


def infer_test_code(path):
    """Derive the test code from the result filename.

    Example:
      result_2026-09-15_AMD64 Family 25 Model 97 Stepping 2, AuthenticAMD_0justinNjinmahHighlights.json

    The test code is the text after the final underscore and before .json.
    This is the primary source because that is how the benchmark exports are
    actually named. A non-generic parent directory remains a fallback.
    """
    path = Path(path)
    generic = {
        "dbresults", "results", "result", "resultsjson", "json",
        "benchmark", "benchmarks", "data", "output", "out",
    }

    stem = path.stem.strip()
    if "_" in stem:
        candidate = stem.rsplit("_", 1)[-1].strip()
        if candidate and candidate.lower() not in generic:
            return candidate

    parent_name = path.parent.name.strip()
    if parent_name and parent_name.lower() not in generic:
        return parent_name

    return ""


def load(path):
    path = Path(path)

    with path.open(encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data.get("results"), list):
        raise ValueError("'results' muss eine Liste sein")

    hardware = data.get("hardware", {})
    return {
        "path": path,
        "hardware": hardware,
        "results": data["results"],
        "category": category(hardware),
        "test_code": test_code(data) or infer_test_code(path),
    }


def expand_input_paths(paths):
    result = []

    for raw_path in paths:
        path = Path(raw_path)

        if path.is_dir():
            result.extend(
                sorted(
                    p for p in path.iterdir()
                    if p.is_file() and p.suffix.lower() == ".json"
                )
            )
            continue

        if path.is_file():
            result.append(path)
            continue

        if any(char in raw_path for char in ("*", "?", "[")):
            parent = path.parent
            if not parent.exists():
                parent = Path(".")
            result.extend(
                sorted(
                    p for p in parent.glob(path.name)
                    if p.is_file() and p.suffix.lower() == ".json"
                )
            )
            continue

        result.append(path)

    unique = []
    seen = set()
    for path in result:
        try:
            key = path.resolve()
        except OSError:
            key = path
        if key not in seen:
            seen.add(key)
            unique.append(path)

    return unique


def iteration(dataset, number):
    for result in dataset["results"]:
        try:
            if int(result.get("iteration")) == number:
                return result
        except (TypeError, ValueError):
            pass
    return None


def value(dataset, iteration_number, metric, db, thread, operation):
    result = iteration(dataset, iteration_number)
    if not result:
        return math.nan

    if metric == "exec_time":
        return num((result.get("exec_time") or {}).get(db))

    database = (result.get("results") or {}).get(db) or {}

    if metric == "tps":
        return num(
            ((database.get("tps") or {}).get(str(thread)) or {}).get(
                "successful_transactions_per_second"
            )
        )

    if metric == "queryrate":
        return num(
            ((database.get("queryrate") or {}).get(str(thread)) or {}).get(
                operation
            )
        )

    latency = (
        ((database.get("latency") or {}).get(str(thread)) or {}).get(operation)
        or {}
    )
    return num(latency.get(metric.removeprefix("latency_") + "_ms"))


def hardware_label(dataset):
    hardware = dataset["hardware"]
    cpu = hardware.get("cpu", {})
    ram = hardware.get("ram", {})

    ram_size = num(ram.get("size_gb"))
    ram_freq = num(ram.get("frequency_mhz"))

    text = (
        f"{cpu_name(hardware)} · "
        f"{cpu.get('cores', '?')}C/"
        f"{cpu.get('threads', '?')}T"
    )

    if not math.isnan(ram_size):
        text += f" · {ram_size:.1f} GB"
    if not math.isnan(ram_freq) and ram_freq > 0:
        text += f" DDR5-{int(ram_freq)}" if ram_freq >= 4800 else f" · {int(ram_freq)} MHz RAM"

    return text


def label(dataset, mode, index):
    hardware_text = hardware_label(dataset)
    code = dataset.get("test_code", "")

    if mode == "anonym":
        return hardware_text

    if mode == "competition":
        # Competition mode identifies each group by the actual test code.
        # Do not fall back to "Teilnehmer 1/2/..." when a code is available.
        return code or f"Teilnehmer {index + 1}"

    if code:
        return f"{hardware_text}\n{code}"
    return hardware_text


def dataset_identity(dataset):
    """Stable identity for color assignment."""
    hw = dataset.get("hardware", {})
    cpu = hw.get("cpu", {})
    ram = hw.get("ram", {})
    return (
        cpu.get("processor", ""),
        cpu.get("cores", ""),
        cpu.get("threads", ""),
        (cpu.get("frequency_mhz") or {}).get("max", ""),
        ram.get("size_gb", ""),
        ram.get("frequency_mhz", ""),
    )


def palette_color(index):
    if index < len(BASE_COLORS):
        return BASE_COLORS[index]

    # Continue with well-spaced hues for arbitrarily many benchmark groups.
    hue = (index * 0.618033988749895) % 1.0
    return hsv_to_rgb((hue, 0.58, 0.82))


def color_for(index, db, mode, same_db_color):
    """Return a deterministic color for the selected color mode."""
    if mode == "datenbank":
        return DB_COLORS[db]

    if same_db_color:
        return palette_color(index)

    # Hardware/akribisch mode with separate DB colors: derive a stable variant
    # from the dataset color so SQLite and LiteDB remain distinguishable.
    base = palette_color(index)
    from matplotlib.colors import to_rgb, rgb_to_hsv, hsv_to_rgb as _hsv_to_rgb
    hsv = rgb_to_hsv(to_rgb(base))
    hsv[0] = (hsv[0] + (0.08 if db == "litedb" else 0.0)) % 1.0
    return _hsv_to_rgb(hsv)


def draw(
    ax,
    datasets,
    metric,
    db_mode,
    thread,
    operation,
    mode,
    competitor,
    hardware_groups,
    mean_line,
    color_mode,
    same_db_color,
):
    ax.clear()

    if not datasets:
        ax.text(0.5, 0.5, "Keine Benchmarks geladen", ha="center", va="center")
        ax.set_axis_off()
        return

    datasets = list(datasets)

    rank = {"highend": 0, "midrange": 1, "lowend": 2, "unknown": 3}

    if hardware_groups:
        datasets.sort(
            key=lambda dataset: (
                rank.get(dataset["category"], 9),
                cpu_name(dataset["hardware"]).lower(),
                dataset.get("test_code", "").lower(),
            )
        )

    competitor = (competitor or "").strip().lower()
    for dataset in datasets:
        dataset["is_competitor"] = bool(
            competitor and dataset.get("test_code", "").lower() == competitor
        )

    dbs = DBS if db_mode == "both" else [db_mode]
    number_of_databases = len(dbs)

    # Hardware mode reuses a color for identical hardware; Akribisch mode
    # assigns one color per loaded benchmark dataset.
    color_keys = {}
    for dataset in datasets:
        key = dataset_identity(dataset) if color_mode == "hardware" else str(dataset.get("path", id(dataset)))
        if key not in color_keys:
            color_keys[key] = len(color_keys)

    # Deliberately generous spacing between result groups. With many (e.g. 20)
    # results, the test code and five iteration markers must remain visually
    # separable instead of becoming one dense block.
    bar_width = 0.12 if number_of_databases == 1 else 0.065
    group_width = 5 * number_of_databases * bar_width
    group_gap = max(bar_width * 12, 0.72)

    centers = []
    plotted_values = []

    for dataset_index, dataset in enumerate(datasets):
        center = dataset_index * (group_width + group_gap)
        centers.append(center)
        start = center - group_width / 2

        for iteration_number in range(1, 6):
            for database_index, database in enumerate(dbs):
                x = (
                    start
                    + (
                        (iteration_number - 1) * number_of_databases
                        + database_index
                        + 0.5
                    ) * bar_width
                )

                value_result = value(
                    dataset,
                    iteration_number,
                    metric,
                    database,
                    thread,
                    operation,
                )

                if not math.isnan(value_result):
                    plotted_values.append(value_result)

                bar = ax.bar(
                    x,
                    0 if math.isnan(value_result) else value_result,
                    width=bar_width * 0.88,
                    color=color_for(
                        color_keys[
                            dataset_identity(dataset)
                            if color_mode == "hardware"
                            else str(dataset.get("path", id(dataset)))
                        ],
                        database,
                        color_mode,
                        same_db_color,
                    ),
                    alpha=0.88 if not math.isnan(value_result) else 0.18,
                )

                if dataset["is_competitor"]:
                    bar[0].set_hatch("//")
                    bar[0].set_edgecolor("black")
                    bar[0].set_linewidth(0.8)

    ax.set_xticks(centers)
    ax.set_xticklabels(
        [label(dataset, mode, index) for index, dataset in enumerate(datasets)],
        rotation=0 if mode == "competition" else 18,
        ha="center" if mode == "competition" else "right",
        fontsize=9 if mode == "competition" else 9,
    )
    # Test codes can legitimately contain '$' and other mathtext characters.
    # Tick labels are plain labels, never LaTeX/math expressions.
    for tick_label in ax.get_xticklabels():
        tick_label.set_parse_math(False)

    # Iteration numbers directly below each five-iteration group.
    for center in centers:
        for iteration_number in range(1, 6):
            offset = (iteration_number - 0.5) * number_of_databases * bar_width
            ax.text(
                center - group_width / 2 + offset,
                -0.035,
                str(iteration_number),
                transform=ax.get_xaxis_transform(),
                ha="center",
                va="top",
                fontsize=8,
            )

    # Competition mode: show the test abbreviation explicitly below the bars.
    if mode == "competition":
        for index, dataset in enumerate(datasets):
            code = dataset.get("test_code") or "—"
            ax.text(
                centers[index],
                -0.105,
                code,
                transform=ax.get_xaxis_transform(),
                ha="center",
                va="top",
                fontsize=9,
                fontweight="bold" if dataset["is_competitor"] else "normal",
            )

    # Hardware-level separators and labels.
    if hardware_groups:
        last_category = None
        for index, dataset in enumerate(datasets):
            current = dataset["category"]
            if current != last_category:
                if index:
                    separator_x = (centers[index - 1] + centers[index]) / 2
                    ax.axvline(
                        separator_x,
                        linestyle="--",
                        linewidth=0.9,
                        alpha=0.5,
                    )

                ax.text(
                    centers[index] - group_width / 2,
                    1.01,
                    CATEGORIES.get(current, current),
                    transform=ax.get_xaxis_transform(),
                    ha="left",
                    va="bottom",
                    fontsize=9,
                    fontweight="bold",
                )
                last_category = current

    if mean_line and plotted_values:
        mean_value = sum(plotted_values) / len(plotted_values)
        ax.axhline(
            mean_value,
            linestyle="--",
            linewidth=1.4,
            label=f"Mittelwert ({mean_value:.2f})",
        )

    unit = (
        "ms"
        if metric.startswith("latency_") or metric == "exec_time"
        else "Transaktionen/s" if metric == "tps" else "Operationen/s"
    )

    title = METRICS[metric]
    if metric != "exec_time":
        if metric == "tps":
            title += f" · {thread} Threads"
        else:
            title += f" · {operation.upper()} · {thread} Threads"

    ax.set_title(title)
    ax.set_ylabel(f"{METRICS[metric]} [{unit}]")
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)

    # Deliberately compact legend: only explain encodings that are not already
    # obvious from the x-axis. This avoids one legend entry per hardware system.
    legend_handles = []
    if color_mode == "datenbank":
        if db_mode == "both":
            legend_handles.extend([
                Patch(facecolor=DB_COLORS["sqlite"], label="SQLite"),
                Patch(facecolor=DB_COLORS["litedb"], label="LiteDB"),
            ])
        elif db_mode in DB_LABELS:
            legend_handles.append(Patch(facecolor=DB_COLORS[db_mode], label=DB_LABELS[db_mode]))
    elif db_mode == "both":
        if same_db_color:
            legend_handles.append(Patch(facecolor=BASE_COLORS[0], label="SQLite / LiteDB"))
        else:
            legend_handles.extend([
                Patch(facecolor=BASE_COLORS[0], label="SQLite"),
                Patch(facecolor=BASE_COLORS[1], label="LiteDB"),
            ])
    elif db_mode in DB_LABELS:
        legend_handles.append(Patch(facecolor=BASE_COLORS[0], label=DB_LABELS[db_mode]))

    if mean_line and plotted_values:
        legend_handles.append(Line2D([0], [0], linestyle="--", linewidth=1.4, label="Mittelwert"))

    if mode == "competition" and any(d["is_competitor"] for d in datasets):
        legend_handles.append(Patch(facecolor="white", edgecolor="black", hatch="//", label="Konkurrent"))

    if legend_handles:
        ax.legend(
            handles=legend_handles,
            loc="upper left",
            bbox_to_anchor=(0, 1.0),
            ncol=min(3, len(legend_handles)),
            frameon=True,
            fontsize=8,
        )

    bottom = 0.34 if mode == "competition" else 0.27
    ax.figure.subplots_adjust(bottom=bottom, left=0.09, right=0.98, top=0.90)


def boolean(value):
    value = value.lower()
    if value in ("true", "1", "yes", "ja", "on"):
        return True
    if value in ("false", "0", "no", "nein", "off"):
        return False
    raise argparse.ArgumentTypeError("true/false erwartet")


class App:
    def __init__(
        self,
        root,
        files=(),
        mode="anonym",
        competitor="",
        groups=True,
        mean_line=False,
        color_mode="hardware",
        same_db_color=True,
    ):
        self.root = root
        root.title("SQLite vs. LiteDB – Benchmark Visualizer")
        root.geometry("1550x930")

        self.ds = []
        self.metric = tk.StringVar(value="queryrate")
        self.db = tk.StringVar(value="sqlite")
        self.thread = tk.StringVar(value="1")
        self.op = tk.StringVar(value="select")
        self.mode = tk.StringVar(value=mode)
        self.comp = tk.StringVar(value=competitor)
        self.groups = tk.BooleanVar(value=groups)
        self.mean_line = tk.BooleanVar(value=mean_line)
        self.color_mode = tk.StringVar(value=color_mode)
        self.same_db_color = tk.BooleanVar(value=same_db_color)

        frame = ttk.Frame(root, padding=8)
        frame.pack(fill="x")

        ttk.Button(frame, text="JSON laden", command=self.select).grid(row=0, column=0, padx=4)
        ttk.Button(frame, text="Alles löschen", command=self.clear).grid(row=0, column=1, padx=4)

        self.file_panel_button = ttk.Button(
            frame,
            text="Dateiübersicht ausblenden",
            command=self.toggle_file_panel,
        )
        self.file_panel_button.grid(row=0, column=2, padx=4)

        controls = [
            (3, "Metrik", self.metric, list(METRICS)),
            (5, "DB", self.db, ["sqlite", "litedb", "both"]),
            (7, "Threads", self.thread, ["1", "2", "4", "8", "16"]),
            (9, "Operation", self.op, OPS),
        ]
        for column, text, variable, values in controls:
            ttk.Label(frame, text=text + ":").grid(row=0, column=column, padx=(18, 3))
            ttk.Combobox(
                frame, textvariable=variable, values=values,
                state="readonly", width=14,
            ).grid(row=0, column=column + 1)

        ttk.Label(frame, text="Modus:").grid(row=1, column=0, sticky="w")
        ttk.Combobox(
            frame, textvariable=self.mode,
            values=["anonym", "competition", "normal"],
            state="readonly", width=14,
        ).grid(row=1, column=1)

        ttk.Label(frame, text="Konkurrenz-Code:").grid(row=1, column=2, padx=(18, 3))
        ttk.Entry(frame, textvariable=self.comp, width=20).grid(row=1, column=3)

        ttk.Label(frame, text="Farbmodus:").grid(row=1, column=4, padx=(18, 3))
        ttk.Combobox(
            frame, textvariable=self.color_mode,
            values=list(COLOR_MODES), state="readonly", width=14,
        ).grid(row=1, column=5)

        ttk.Checkbutton(
            frame, text="SQLite/LiteDB gleiche Farbe", variable=self.same_db_color,
        ).grid(row=1, column=6, padx=(18, 3), sticky="w")
        ttk.Label(
            frame, text="Datenbank-Modus = feste SQLite/LiteDB-Farben",
        ).grid(row=1, column=7, padx=(12, 3), sticky="w")

        options = ttk.Frame(root, padding=(8, 0, 8, 4))
        options.pack(fill="x")
        ttk.Checkbutton(
            options, text="Hardware-Level gruppieren", variable=self.groups,
        ).pack(side="left", padx=(0, 18))
        ttk.Checkbutton(
            options, text="Mittelwertlinie", variable=self.mean_line,
        ).pack(side="left")

        # The file overview can be collapsed to give the chart the full width.
        self.left_visible = True

        left = ttk.Frame(root, padding=8)
        self.left = left
        left.pack(side="left", fill="y")
        ttk.Label(left, text="Geladene Benchmarks").pack(anchor="w")

        self.tree = ttk.Treeview(
            left,
            columns=("category", "cpu", "test"),
            show="headings",
            height=30,
        )
        for column, title in [
            ("category", "Hardware-Level"),
            ("cpu", "CPU / RAM"),
            ("test", "Testkürzel"),
        ]:
            self.tree.heading(column, text=title)
        self.tree.column("category", width=105)
        self.tree.column("cpu", width=315)
        self.tree.column("test", width=125)
        self.tree.pack(fill="y", expand=True)

        right = ttk.Frame(root, padding=8)
        self.right = right
        right.pack(side="right", fill="both", expand=True)

        self.fig, self.ax = plt.subplots(figsize=(12, 7))
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        variables = [
            self.metric, self.db, self.thread, self.op, self.mode, self.comp,
            self.groups, self.mean_line, self.color_mode, self.same_db_color,
        ]
        for variable in variables:
            variable.trace_add("write", lambda *_: self.draw())

        self.load(files)

    def toggle_file_panel(self):
        """Show or hide the left file overview."""
        if self.left_visible:
            self.left.pack_forget()
            self.left_visible = False
            self.file_panel_button.configure(text="Dateiübersicht einblenden")
        else:
            self.left.pack(side="left", fill="y", before=self.right)
            self.left_visible = True
            self.file_panel_button.configure(text="Dateiübersicht ausblenden")

        self.root.update_idletasks()
        self.canvas.draw_idle()

    def select(self):
        paths = filedialog.askopenfilenames(
            filetypes=[("JSON", "*.json"), ("Alle", "*.*")]
        )
        self.load(paths)

    def load(self, paths):
        errors = []
        for path in expand_input_paths(paths):
            try:
                self.ds.append(load(path))
            except Exception as error:
                errors.append(f"{Path(path).name}: {error}")

        self.tree.delete(*self.tree.get_children())
        for dataset in self.ds:
            self.tree.insert(
                "", "end",
                values=(
                    CATEGORIES.get(dataset["category"], "Unbekannt"),
                    hardware_label(dataset),
                    dataset["test_code"] or "—",
                ),
            )

        self.draw()
        if errors:
            messagebox.showerror("Fehler", "\n".join(errors))

    def clear(self):
        self.ds.clear()
        self.tree.delete(*self.tree.get_children())
        self.draw()

    def draw(self):
        draw(
            self.ax,
            self.ds,
            self.metric.get(),
            self.db.get(),
            int(self.thread.get()),
            self.op.get(),
            self.mode.get(),
            self.comp.get(),
            self.groups.get(),
            self.mean_line.get(),
            self.color_mode.get(),
            self.same_db_color.get(),
        )
        self.canvas.draw_idle()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "files", nargs="*",
        help="JSON-Dateien, JSON-Wildcards oder Ordner mit JSON-Dateien",
    )
    parser.add_argument(
        "--type", choices=["anonym", "competition", "normal"], default="anonym",
    )
    parser.add_argument("--competitor", default="")
    parser.add_argument(
        "--enableSpecificationGroups", type=boolean, default=True,
        help="Kompatibilitätsalias für Hardware-Level-Gruppierung",
    )
    parser.add_argument(
        "--mean-line", type=boolean, default=False,
        help="Mittelwertlinie ein-/ausschalten",
    )
    parser.add_argument(
        "--color-mode", choices=list(COLOR_MODES), default="hardware",
    )
    parser.add_argument(
        "--same-db-color", type=boolean, default=True,
        help="SQLite und LiteDB innerhalb eines Benchmarks gleich einfärben; Datenbank-Modus verwendet feste globale Farben",
    )
    parser.add_argument("--metric", choices=list(METRICS), default="queryrate")
    parser.add_argument("--db", choices=["sqlite", "litedb", "both"], default="sqlite")
    parser.add_argument("--threads", type=int, choices=[1, 2, 4, 8, 16], default=1)
    parser.add_argument("--operation", choices=OPS, default="select")

    args = parser.parse_args()
    root = tk.Tk()
    app = App(
        root,
        args.files,
        args.type,
        args.competitor,
        args.enableSpecificationGroups,
        args.mean_line,
        args.color_mode,
        args.same_db_color,
    )
    app.metric.set(args.metric)
    app.db.set(args.db)
    app.thread.set(str(args.threads))
    app.op.set(args.operation)
    root.mainloop()


if __name__ == "__main__":
    main()
