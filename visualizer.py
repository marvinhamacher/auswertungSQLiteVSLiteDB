from __future__ import annotations

import argparse
import json
import math
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

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


CUSTOM_CPU_CATEGORY_MAP = {}


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

    score = score_hardware(hw)

    if score <= 349:
        return "lowend"

    if score <= 649:
        return "midrange"

    return "highend"


def cpu_name(hw):
    return get_cpu_display_name(hw)


def test_code(data):
    keys = [
        "test_code",
        "testCode",
        "test_id",
        "testId",
        "testkürzel",
        "testkuerzel",
        "code",
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




def test_code_from_path(path: Path) -> str:
    """Ermittelt das Testkürzel aus dbresults/<Kürzel>/<datei>.json."""
    for parent in path.resolve().parents:
        if parent.name.lower() == "dbresults":
            code = path.resolve().parent.name
            if code and code.lower() != "dbresults":
                return code
            break

    return ""


def load(path):
    path = Path(path)

    with path.open(encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data.get("results"), list):
        raise ValueError("'results' muss eine Liste sein")

    return {
        "path": path,
        "hardware": data.get("hardware", {}),
        "results": data["results"],
        "category": category(data.get("hardware", {})),
        "test_code": (
            test_code(data)
            or test_code_from_path(path)
        ),
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

            pattern = path.name

            result.extend(
                sorted(
                    p for p in parent.glob(pattern)
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
            (
                (database.get("tps") or {}).get(str(thread))
                or {}
            ).get("successful_transactions_per_second")
        )

    if metric == "queryrate":
        return num(
            (
                (database.get("queryrate") or {}).get(str(thread))
                or {}
            ).get(operation)
        )

    latency = (
        (database.get("latency") or {}).get(str(thread))
        or {}
    ).get(operation) or {}

    return num(
        latency.get(
            metric.removeprefix("latency_") + "_ms"
        )
    )


def label(dataset, mode, index):
    hardware = dataset["hardware"]

    cpu = hardware.get("cpu", {})
    ram = hardware.get("ram", {})

    ram_size = num(ram.get("size_gb"))

    if not math.isnan(ram_size):
        hardware_label = (
            f"{cpu_name(hardware)} · "
            f"{cpu.get('cores', '?')}C/"
            f"{cpu.get('threads', '?')}T · "
            f"{ram_size:.1f} GB"
        )
    else:
        hardware_label = (
            f"{cpu_name(hardware)} · "
            f"{cpu.get('cores', '?')}C/"
            f"{cpu.get('threads', '?')}T"
        )

    if mode == "anonym":
        return hardware_label

    if mode == "competition":
        return dataset.get("test_code") or f"Teilnehmer {index + 1}"

    if dataset.get("test_code"):
        return hardware_label + f"\n{dataset['test_code']}"

    return hardware_label


def draw(
    ax,
    datasets,
    metric,
    db_mode,
    thread,
    operation,
    mode,
    competitor,
    groups,
):
    ax.clear()

    if not datasets:
        ax.text(
            0.5,
            0.5,
            "Keine Benchmarks geladen",
            ha="center",
            va="center",
        )
        ax.set_axis_off()
        return

    datasets = list(datasets)

    rank = {
        "highend": 0,
        "midrange": 1,
        "lowend": 2,
        "unknown": 3,
    }

    if groups:
        datasets.sort(
            key=lambda dataset: (
                rank.get(dataset["category"], 9),
                label(dataset, "normal", 0).lower(),
            )
        )

    competitor = (competitor or "").strip().lower()

    for dataset in datasets:
        dataset["is_competitor"] = bool(
            competitor
            and dataset.get("test_code", "").lower() == competitor
        )

    dbs = DBS if db_mode == "both" else [db_mode]

    number_of_databases = len(dbs)

    bar_width = (
        0.14
        if number_of_databases == 1
        else 0.075
    )

    group_width = (
        5
        * number_of_databases
        * bar_width
    )

    gap = bar_width * 9

    centers = []

    for dataset_index, dataset in enumerate(datasets):
        center = dataset_index * (group_width + gap)
        centers.append(center)

        start = center - group_width / 2

        for iteration_number in range(1, 6):
            for database_index, database in enumerate(dbs):
                x = (
                    start
                    + (
                        (iteration_number - 1)
                        * number_of_databases
                        + database_index
                        + 0.5
                    )
                    * bar_width
                )

                value_result = value(
                    dataset,
                    iteration_number,
                    metric,
                    database,
                    thread,
                    operation,
                )

                bar = ax.bar(
                    x,
                    0 if math.isnan(value_result) else value_result,
                    width=bar_width * 0.9,
                    label=(
                        DB_LABELS[database]
                        if dataset_index == 0
                        else None
                    ),
                )

                if dataset["is_competitor"]:
                    bar[0].set_hatch("//")

                if math.isnan(value_result):
                    bar[0].set_alpha(0.15)

    ax.set_xticks(centers)

    ax.set_xticklabels(
        [
            label(dataset, mode, index)
            for index, dataset in enumerate(datasets)
        ],
        rotation=35 if mode != "competition" else 0,
        ha="right" if mode != "competition" else "center",
        fontsize=9 if mode != "competition" else 10,
    )

    for center in centers:
        for iteration_number in range(1, 6):
            offset = (
                (iteration_number - 0.5)
                * number_of_databases
                * bar_width
            )

            ax.text(
                center - group_width / 2 + offset,
                -0.045,
                str(iteration_number),
                transform=ax.get_xaxis_transform(),
                ha="center",
                va="top",
                fontsize=9,
            )

    if groups:
        last_category = None

        for index, dataset in enumerate(datasets):
            if dataset["category"] != last_category:
                if index:
                    ax.axvline(
                        (
                            centers[index - 1]
                            + centers[index]
                        ) / 2,
                        linestyle="--",
                        linewidth=0.8,
                        alpha=0.5,
                    )

                last_category = dataset["category"]

    unit = (
        "ms"
        if metric.startswith("latency_")
        or metric == "exec_time"
        else (
            "Transaktionen/s"
            if metric == "tps"
            else "Operationen/s"
        )
    )

    title = METRICS[metric]

    if metric != "exec_time":
        if metric == "tps":
            title += f" · {thread} Threads"
        else:
            title += (
                f" · {operation.upper()} · "
                f"{thread} Threads"
            )

    ax.set_title(title)
    ax.set_ylabel(
        f"{METRICS[metric]} [{unit}]"
    )

    ax.grid(
        axis="y",
        alpha=0.25,
    )

    ax.set_axisbelow(True)
    ax.legend()

    ax.figure.subplots_adjust(
        bottom=0.24 if mode == "competition" else 0.30,
        left=0.09,
        right=0.98,
        top=0.90,
    )


class App:
    def __init__(
        self,
        root,
        files=(),
        mode="anonym",
        competitor="",
        groups=True,
    ):
        self.root = root

        root.title(
            "SQLite vs. LiteDB – Benchmark Visualizer"
        )

        root.geometry("1450x900")

        self.ds = []

        self.metric = tk.StringVar(
            value="queryrate"
        )

        self.db = tk.StringVar(
            value="sqlite"
        )

        self.thread = tk.StringVar(
            value="1"
        )

        self.op = tk.StringVar(
            value="select"
        )

        self.mode = tk.StringVar(
            value=mode
        )

        self.comp = tk.StringVar(
            value=competitor
        )

        self.groups = tk.BooleanVar(
            value=groups
        )

        frame = ttk.Frame(
            root,
            padding=8,
        )

        frame.pack(fill="x")

        ttk.Button(
            frame,
            text="JSON laden",
            command=self.select,
        ).grid(
            row=0,
            column=0,
            padx=4,
        )

        ttk.Button(
            frame,
            text="Alles löschen",
            command=self.clear,
        ).grid(
            row=0,
            column=1,
            padx=4,
        )

        self.file_panel_button = ttk.Button(
            frame,
            text="Dateiübersicht ausblenden",
            command=self.toggle_file_panel,
        )
        self.file_panel_button.grid(
            row=0,
            column=2,
            padx=4,
        )

        controls = [
            (
                3,
                "Metrik",
                self.metric,
                list(METRICS),
            ),
            (
                5,
                "DB",
                self.db,
                ["sqlite", "litedb", "both"],
            ),
            (
                7,
                "Threads",
                self.thread,
                ["1", "2", "4", "8", "16"],
            ),
            (
                9,
                "Operation",
                self.op,
                OPS,
            ),
        ]

        for column, text, variable, values in controls:
            ttk.Label(
                frame,
                text=text + ":",
            ).grid(
                row=0,
                column=column,
                padx=(18, 3),
            )

            ttk.Combobox(
                frame,
                textvariable=variable,
                values=values,
                state="readonly",
                width=14,
            ).grid(
                row=0,
                column=column + 1,
            )

        ttk.Label(
            frame,
            text="Modus:",
        ).grid(
            row=1,
            column=0,
        )

        ttk.Combobox(
            frame,
            textvariable=self.mode,
            values=[
                "anonym",
                "competition",
                "normal",
            ],
            state="readonly",
            width=14,
        ).grid(
            row=1,
            column=1,
        )

        ttk.Label(
            frame,
            text="Konkurrenz-Code:",
        ).grid(
            row=1,
            column=2,
            padx=(18, 3),
        )

        ttk.Entry(
            frame,
            textvariable=self.comp,
            width=20,
        ).grid(
            row=1,
            column=3,
        )

        ttk.Checkbutton(
            frame,
            text="Specification-Gruppen",
            variable=self.groups,
        ).grid(
            row=1,
            column=4,
            columnspan=2,
            sticky="w",
            padx=18,
        )

        self.left_visible = True

        left = ttk.Frame(
            root,
            padding=8,
        )

        self.left = left

        left.pack(
            side="left",
            fill="y",
        )

        ttk.Label(
            left,
            text="Geladene Benchmarks",
        ).pack(
            anchor="w"
        )

        self.tree = ttk.Treeview(
            left,
            columns=(
                "category",
                "cpu",
                "test",
            ),
            show="headings",
            height=28,
        )

        for column, title in [
            ("category", "Kategorie"),
            ("cpu", "CPU"),
            ("test", "Test"),
        ]:
            self.tree.heading(
                column,
                text=title,
            )

        self.tree.column(
            "category",
            width=95,
        )

        self.tree.column(
            "cpu",
            width=250,
        )

        self.tree.column(
            "test",
            width=100,
        )

        self.tree.pack(
            fill="y",
            expand=True,
        )

        right = ttk.Frame(
            root,
            padding=8,
        )

        self.right = right

        right.pack(
            side="right",
            fill="both",
            expand=True,
        )

        self.fig, self.ax = plt.subplots(
            figsize=(12, 7)
        )

        self.canvas = FigureCanvasTkAgg(
            self.fig,
            master=right,
        )

        self.canvas.get_tk_widget().pack(
            fill="both",
            expand=True,
        )

        variables = [
            self.metric,
            self.db,
            self.thread,
            self.op,
            self.mode,
            self.comp,
            self.groups,
        ]

        for variable in variables:
            variable.trace_add(
                "write",
                lambda *_: self.draw(),
            )

        self.load(files)

    def toggle_file_panel(self):

        if self.left_visible:
            self.left.pack_forget()
            self.left_visible = False
            self.file_panel_button.configure(
                text="Dateiübersicht einblenden"
            )
        else:
            self.left.pack(
                side="left",
                fill="y",
                before=self.right,
            )
            self.left_visible = True
            self.file_panel_button.configure(
                text="Dateiübersicht ausblenden"
            )

        self.root.update_idletasks()
        self.canvas.draw_idle()

    def select(self):
        paths = filedialog.askopenfilenames(
            filetypes=[
                ("JSON", "*.json"),
                ("Alle", "*.*"),
            ]
        )

        self.load(paths)

    def load(self, paths):
        expanded_paths = expand_input_paths(paths)

        errors = []

        for path in expanded_paths:
            try:
                self.ds.append(load(path))
            except Exception as error:
                errors.append(
                    f"{Path(path).name}: {error}"
                )

        self.tree.delete(
            *self.tree.get_children()
        )

        for dataset in self.ds:
            self.tree.insert(
                "",
                "end",
                values=(
                    CATEGORIES[
                        dataset["category"]
                    ],
                    cpu_name(
                        dataset["hardware"]
                    ),
                    dataset["test_code"] or "—",
                ),
            )

        self.draw()

        if errors:
            messagebox.showerror(
                "Fehler",
                "\n".join(errors),
            )

    def clear(self):
        self.ds.clear()

        self.tree.delete(
            *self.tree.get_children()
        )

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
        )

        self.canvas.draw_idle()


def boolean(value):
    value = value.lower()

    if value in (
        "true",
        "1",
        "yes",
        "ja",
        "on",
    ):
        return True

    if value in (
        "false",
        "0",
        "no",
        "nein",
        "off",
    ):
        return False

    raise argparse.ArgumentTypeError(
        "true/false erwartet"
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "files",
        nargs="*",
        help=(
            "JSON-Dateien, JSON-Wildcards oder "
            "Ordner mit JSON-Dateien"
        ),
    )

    parser.add_argument(
        "--type",
        choices=[
            "anonym",
            "competition",
            "normal",
        ],
        default="anonym",
    )

    parser.add_argument(
        "--competitor",
        default="",
    )

    parser.add_argument(
        "--enableSpecificationGroups",
        type=boolean,
        default=True,
    )

    parser.add_argument(
        "--metric",
        choices=list(METRICS),
        default="queryrate",
    )

    parser.add_argument(
        "--db",
        choices=[
            "sqlite",
            "litedb",
            "both",
        ],
        default="sqlite",
    )

    parser.add_argument(
        "--threads",
        type=int,
        choices=[
            1,
            2,
            4,
            8,
            16,
        ],
        default=1,
    )

    parser.add_argument(
        "--operation",
        choices=OPS,
        default="select",
    )

    args = parser.parse_args()

    root = tk.Tk()

    app = App(
        root,
        args.files,
        args.type,
        args.competitor,
        args.enableSpecificationGroups,
    )

    app.metric.set(args.metric)
    app.db.set(args.db)
    app.thread.set(str(args.threads))
    app.op.set(args.operation)

    root.mainloop()


if __name__ == "__main__":
    main()

