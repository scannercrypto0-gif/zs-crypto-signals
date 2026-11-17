"""Read local evidence and safely start/stop the fixed offline diagnostics."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from tkinter import Tk, StringVar
from tkinter import ttk

FIELDS = (
    ("Binance", "HISTORICAL_SOURCE_PROVEN / CURRENT_NOT_EVALUATED"),
    ("Independent time", "BLOCKED"), ("Qualification", "BLOCKED"),
    ("Qualified / rejected live signals", "NOT_EVALUATED"),
    ("Telegram A / B / C", "NOT_EVALUATED"), ("GitHub operational archive", "NOT_EVALUATED"),
    ("SQL", "NOT_EVALUATED"), ("Outcome evaluator", "NOT_EVALUATED"),
    ("Pending operations", "NOT_EVALUATED"), ("Resource metrics", "NOT_EVALUATED"),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if os.name != "nt" or output.drive.upper() != "D:":
        parser.error("Windows output on D: is required")
    output.mkdir()
    repo = Path(__file__).resolve().parents[1]
    window = Tk()
    window.title("SMART GATE — Offline diagnostics")
    frame = ttk.Frame(window, padding=16)
    frame.grid(sticky="nsew")
    state = StringVar(value="Offline diagnostics idle")
    ttk.Label(frame, textvariable=state).grid(row=0, columnspan=2, sticky="w", pady=(0, 12))
    for index, (name, value) in enumerate(FIELDS, 1):
        ttk.Label(frame, text=name).grid(row=index, column=0, sticky="w", padx=(0, 12))
        ttk.Label(frame, text=value).grid(row=index, column=1, sticky="w")
    process, attempts, stopped = None, 0, False
    streams = []

    def poll():
        nonlocal process
        code = process.poll()
        if code is None:
            window.after(200, poll)
            return
        for stream in streams:
            stream.close()
        streams.clear()
        record = {"exit": code, "stopped": stopped, "scope": "OFFLINE_DIAGNOSTICS"}
        (output/f"run-{attempts}-exit.json").write_text(json.dumps(record), encoding="utf-8")
        state.set("Stopped" if stopped else f"Offline diagnostics finished • EXIT {code}")
        process = None
        start_button.state(["!disabled"])
        stop_button.state(["disabled"])

    def start():
        nonlocal process, attempts, stopped
        if process is not None:
            return
        attempts += 1
        stopped = False
        env = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "PATH") if key in os.environ}
        env.update(PYTHONPATH=os.pathsep.join((str(repo/"src"), str(repo/"tests"))),
                   PYTHONDONTWRITEBYTECODE="1", TEMP=str(output), TMP=str(output))
        try:
            for name in ("stdout", "stderr"):
                streams.append((output/f"run-{attempts}-{name}.txt").open("xb"))
            process = subprocess.Popen([sys.executable, "-m", "unittest", "-v",
                                        "test_ops_signals_readiness", "test_stage13_operational_harness",
                                        "test_ops_clock_recorded"],
                                       cwd=repo, env=env, stdout=streams[0], stderr=streams[1],
                                       creationflags=subprocess.CREATE_NO_WINDOW)
        except OSError:
            for stream in streams:
                stream.close()
            streams.clear()
            state.set("Offline diagnostics could not start")
            return
        state.set("Offline diagnostics running")
        start_button.state(["disabled"])
        stop_button.state(["!disabled"])
        window.after(200, poll)

    def stop():
        nonlocal stopped
        if process is not None and process.poll() is None:
            stopped = True
            process.terminate()
            state.set("Stopping offline diagnostics")

    def close():
        if process is not None:
            stop()
            window.after(250, close)
        else:
            window.destroy()

    start_button = ttk.Button(frame, text="Start offline checks", command=start)
    start_button.grid(row=len(FIELDS)+1, column=0, sticky="w", pady=(12, 0))
    stop_button = ttk.Button(frame, text="Stop checks", command=stop)
    stop_button.grid(row=len(FIELDS)+1, column=1, sticky="w", pady=(12, 0))
    stop_button.state(["disabled"])
    window.protocol("WM_DELETE_WINDOW", close)
    window.mainloop()


if __name__ == "__main__":
    main()
