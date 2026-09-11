import json
import math
import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

PERFORMANCE_CATEGORY_MAP = {
    "lowend": {"label": "Low-end", "max_score": 349},
    "midrange": {"label": "Mid-range", "max_score": 649},
    "highend": {"label": "High-end", "max_score": 9999},
}

CPU_SCORE_MAP = {
    "AMD64 Family 25 Model 97 Stepping 2, AuthenticAMD": 700,
}

CUSTOM_CPU_CATEGORY_MAP = {
    "AMD64 Family 25 Model 97 Stepping 2, AuthenticAMD": "highend",
}

CATEGORY_ORDER = ["lowend", "midrange", "highend"]
DB_ORDER = ["sqlite", "litedb"]

METRICS = [
    "Execution time",
    "TPS",
    "Query rate",
    "Latency average",
    "Latency minimum",
    "Latency maximum",
]


def fnum(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def cpu_text(hw):
    return str(hw.get("cpu", {}).get("processor", "")).strip()


def score_hardware(hw):
    cpu = hw.get("cpu", {})
    cpu_name = cpu_text(hw)
    if cpu_name in CPU_SCORE_MAP:
        return CPU_SCORE_MAP[cpu_name]
    cores = fnum(cpu.get("cores"))
    threads = fnum(cpu.get("threads"))
    freq = fnum(cpu.get("frequency_mhz", {}).get("max"))
    ram = fnum(hw.get("ram", {}).get("size_gb"))
    score = 45 * (0 if math.isnan(cores) else cores)
    score += 20 * (0 if math.isnan(threads) else threads)
    score += 0.08 * (0 if math.isnan(freq) else freq)
    score += 8 * (0 if math.isnan(ram) else ram)
    return score


def classify_hardware(hw):
    exact = CUSTOM_CPU_CATEGORY_MAP.get(cpu_text(hw))
    if exact:
        return exact
    score = score_hardware(hw)
    for category in CATEGORY_ORDER:
        if score <= PERFORMANCE_CATEGORY_MAP[category]["max_score"]:
            return category
    return "highend"


def load_dataset(path):
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return {
        "name": Path(path).stem,
        "path": str(path),
        "hardware": data.get("hardware", {}),
        "category": classify_hardware(data.get("hardware", {})),
        "results": data.get("results", []),
    }


def flatten(datasets):
    rows = []
    for ds in datasets:
        for result in ds["results"]:
            iteration = result.get("iteration")
            exec_time = result.get("exec_time", {})
            for db in DB_ORDER:
                block = result.get("results", {}).get(db, {})
                if db in exec_time:
                    rows.append({
                        "dataset": ds["name"], "category": ds["category"], "db": db,
                        "metric": "Execution time", "thread": None, "operation": "total",
                        "iteration": iteration, "value": fnum(exec_time[db])
                    })
                for thread, item in block.get("tps", {}).items():
                    rows.append({
                        "dataset": ds["name"], "category": ds["category"], "db": db,
                        "metric": "TPS", "thread": int(thread), "operation": "transaction",
                        "iteration": iteration,
                        "value": fnum(item.get("successful_transactions_per_second"))
                    })
                for thread, ops in block.get("queryrate", {}).items():
                    for op, value in ops.items():
                        rows.append({
                            "dataset": ds["name"], "category": ds["category"], "db": db,
                            "metric": "Query rate", "thread": int(thread), "operation": op,
                            "iteration": iteration, "value": fnum(value)
                        })
                for thread, ops in block.get("latency", {}).items():
                    for op, stats in ops.items():
                        for stat, metric_name in {
                            "avg_ms": "Latency average",
                            "min_ms": "Latency minimum",
                            "max_ms": "Latency maximum",
                        }.items():
                            rows.append({
                                "dataset": ds["name"], "category": ds["category"], "db": db,
                                "metric": metric_name, "thread": int(thread), "operation": op,
                                "iteration": iteration, "value": fnum(stats.get(stat))
                            })
    return rows


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("SQLite vs LiteDB Benchmark Visualizer")
        self.root.geometry("1500x950")
        self.datasets = []
        self.rows = []
        self.figure = None
        self.metric = tk.StringVar(value="TPS")
        self.thread = tk.StringVar(value="All")
        self.operation = tk.StringVar(value="All")
        self.iteration = tk.StringVar(value="All")
        self.chart_type = tk.StringVar(value="bar")
        self.build()

    def build(self):
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")
        ttk.Button(top, text="JSON-Dateien laden", command=self.load_files).pack(side="left", padx=3)
        ttk.Button(top, text="Grafik speichern", command=self.save).pack(side="left", padx=3)
        ttk.Label(top, text="Metric").pack(side="left", padx=(18, 3))
        metric_box = ttk.Combobox(top, textvariable=self.metric, values=METRICS, state="readonly", width=18)
        metric_box.pack(side="left")
        metric_box.bind("<<ComboboxSelected>>", lambda _: self.refresh_filters())
        ttk.Label(top, text="Threads").pack(side="left", padx=(12, 3))
        self.thread_box = ttk.Combobox(top, textvariable=self.thread, values=["All"], state="readonly", width=8)
        self.thread_box.pack(side="left")
        ttk.Label(top, text="Operation").pack(side="left", padx=(12, 3))
        self.operation_box = ttk.Combobox(top, textvariable=self.operation, values=["All"], state="readonly", width=14)
        self.operation_box.pack(side="left")
        ttk.Label(top, text="Iteration").pack(side="left", padx=(12, 3))
        self.iteration_box = ttk.Combobox(top, textvariable=self.iteration, values=["All"], state="readonly", width=8)
        self.iteration_box.pack(side="left")
        ttk.Radiobutton(top, text="Balken", variable=self.chart_type, value="bar", command=self.draw).pack(side="left", padx=(18, 3))
        ttk.Radiobutton(top, text="Plot", variable=self.chart_type, value="plot", command=self.draw).pack(side="left", padx=3)
        ttk.Button(top, text="Aktualisieren", command=self.draw).pack(side="left", padx=5)

        pane = ttk.PanedWindow(self.root, orient="horizontal")
        pane.pack(fill="both", expand=True)
        left = ttk.Frame(pane, padding=8)
        right = ttk.Frame(pane, padding=8)
        pane.add(left, weight=1)
        pane.add(right, weight=4)
        ttk.Label(left, text="Geladene Benchmarks", font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        self.tree = ttk.Treeview(left, columns=("file", "category", "cpu", "ram"), show="headings")
        for col, title, width in [("file", "Datei", 160), ("category", "Kategorie", 90), ("cpu", "CPU", 170), ("ram", "RAM", 70)]:
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width)
        self.tree.pack(fill="both", expand=True)
        ttk.Label(left, text="Performance-Mapping", font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(12, 3))
        ttk.Label(left, text="CUSTOM_CPU_CATEGORY_MAP zuerst; sonst Score aus CPU/Cores/Threads/Frequenz/RAM.", wraplength=300, justify="left").pack(anchor="w")
        self.info = ttk.Label(right, text="Noch keine Daten geladen.")
        self.info.pack(fill="x")
        self.chart_frame = ttk.Frame(right)
        self.chart_frame.pack(fill="both", expand=True, pady=(8, 0))

    def load_files(self):
        paths = filedialog.askopenfilenames(filetypes=[("JSON", "*.json"), ("Alle Dateien", "*.*")])
        if not paths:
            return
        loaded, errors = [], []
        for path in paths:
            try:
                loaded.append(load_dataset(path))
            except Exception as exc:
                errors.append(f"{Path(path).name}: {exc}")
        if errors:
            messagebox.showwarning("Importwarnung", "\n".join(errors))
        self.datasets = loaded
        self.rows = flatten(self.datasets)
        self.refresh_tree()
        self.refresh_filters()
        self.draw()

    def refresh_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for ds in sorted(self.datasets, key=lambda x: (CATEGORY_ORDER.index(x["category"]), x["name"])):
            hw = ds["hardware"]
            self.tree.insert("", "end", values=(
                ds["name"], PERFORMANCE_CATEGORY_MAP[ds["category"]]["label"],
                cpu_text(hw)[:28], f'{hw.get("ram", {}).get("size_gb", "?")} GB'
            ))
        self.info.config(text=f"{len(self.datasets)} Benchmark-Datei(en), {len(self.rows)} Datenpunkte geladen.")

    def refresh_filters(self):
        rows = [r for r in self.rows if r["metric"] == self.metric.get()]
        threads = [str(x) for x in sorted({r["thread"] for r in rows if r["thread"] is not None})]
        ops = sorted({r["operation"] for r in rows})
        iters = [str(x) for x in sorted({r["iteration"] for r in rows if r["iteration"] is not None})]
        self.thread_box["values"] = ["All"] + threads
        self.operation_box["values"] = ["All"] + ops
        self.iteration_box["values"] = ["All"] + iters
        for var, values in [(self.thread, ["All"] + threads), (self.operation, ["All"] + ops), (self.iteration, ["All"] + iters)]:
            if var.get() not in values:
                var.set("All")

    def filtered(self):
        rows = [r for r in self.rows if r["metric"] == self.metric.get()]
        if self.thread.get() != "All":
            rows = [r for r in rows if r["thread"] == int(self.thread.get())]
        if self.operation.get() != "All":
            rows = [r for r in rows if r["operation"] == self.operation.get()]
        if self.iteration.get() != "All":
            rows = [r for r in rows if r["iteration"] == int(self.iteration.get())]
        return [r for r in rows if not math.isnan(r["value"])]

    def draw(self):
        if not self.datasets:
            return
        rows = self.filtered()
        if not rows:
            return
        for child in self.chart_frame.winfo_children():
            child.destroy()
        self.figure = plt.Figure(figsize=(11, 6.5), dpi=100)
        ax = self.figure.add_subplot(111)
        if self.chart_type.get() == "bar":
            self.draw_bar(ax, rows)
        else:
            self.draw_plot(ax, rows)
        self.figure.tight_layout()
        canvas = FigureCanvasTkAgg(self.figure, master=self.chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def draw_bar(self, ax, rows):
        ordered = sorted(rows, key=lambda r: (CATEGORY_ORDER.index(r["category"]), r["dataset"], DB_ORDER.index(r["db"]), r["iteration"] or 0, r["thread"] or 0, r["operation"]))
        labels, values = [], []
        for r in ordered:
            title = r["dataset"][:16]
            details = [r["db"]]
            if r["iteration"] is not None:
                details.append(f"i{r["iteration"]}")
            if r["thread"] is not None:
                details.append(f"{r["thread"]}T")
            if r["operation"] != "total":
                details.append(r["operation"])
            labels.append(title + "\n" + " ".join(details))
            values.append(r["value"])
        x = np.arange(len(values))
        ax.bar(x, values)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=70, ha="right", fontsize=7)
        ax.set_ylabel("ms" if "Latency" in self.metric.get() or self.metric.get() == "Execution time" else ("tx/s" if self.metric.get() == "TPS" else "ops/s"))
        ax.set_title(f"{self.metric.get()} – alle Ergebnisse")
        ax.grid(axis="y", alpha=0.25)
        seen = []
        for r in ordered:
            if r["category"] in seen:
                continue
            seen.append(r["category"])
        for cat in CATEGORY_ORDER:
            positions = [i for i, r in enumerate(ordered) if r["category"] == cat]
            if positions:
                ax.text((positions[0] + positions[-1]) / 2, 1.02, PERFORMANCE_CATEGORY_MAP[cat]["label"], transform=ax.get_xaxis_transform(), ha="center", va="bottom", fontweight="bold")

    def draw_plot(self, ax, rows):
        if self.thread.get() == "All":
            threads = sorted({r["thread"] for r in rows if r["thread"] is not None})
        else:
            threads = [int(self.thread.get())]
        series = {}
        for r in rows:
            if r["thread"] is None:
                continue
            key = (r["dataset"], r["db"], r["operation"], r["iteration"])
            series.setdefault(key, {})[r["thread"]] = r["value"]
        for (dataset, db, operation, iteration), points in sorted(series.items()):
            xs = [t for t in threads if t in points]
            ys = [points[t] for t in xs]
            label = f"{dataset} | {db}"
            if self.metric.get() != "TPS":
                label += f" | {operation}"
            if iteration is not None and self.iteration.get() == "All":
                label += f" | i{iteration}"
            ax.plot(xs, ys, marker="o", linewidth=1.8, label=label)
        ax.set_xlabel("Threads")
        ax.set_ylabel("ms" if "Latency" in self.metric.get() else ("tx/s" if self.metric.get() == "TPS" else "ops/s"))
        ax.set_title(f"{self.metric.get()} – Skalierung")
        ax.set_xticks(threads)
        ax.grid(alpha=0.25)
        if len(series) <= 20:
            ax.legend(fontsize=7, loc="best")

    def save(self):
        if self.figure is None:
            return
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png"), ("SVG", "*.svg"), ("PDF", "*.pdf")])
        if path:
            self.figure.savefig(path, dpi=200, bbox_inches="tight")


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
