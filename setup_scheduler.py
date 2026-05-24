"""
Run this once to register a Windows Task Scheduler job that executes
naukri_bot.py every day at the time you choose.

Usage:
    python setup_scheduler.py            # prompts for time
    python setup_scheduler.py --time 09:30
    python setup_scheduler.py --delete   # removes the task
"""

import sys
import subprocess
import argparse
from pathlib import Path

TASK_NAME = "NaukriDailyApply"
BOT_SCRIPT = Path(__file__).parent / "naukri_bot.py"
PYTHON_EXE = sys.executable


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def create_task(run_time: str):
    # Validate HH:MM
    parts = run_time.split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        print(f"Invalid time '{run_time}'. Use HH:MM format (e.g. 09:00)")
        sys.exit(1)

    cmd = [
        "schtasks", "/create",
        "/tn", TASK_NAME,
        "/tr", f'"{PYTHON_EXE}" "{BOT_SCRIPT}"',
        "/sc", "DAILY",
        "/st", run_time,
        "/rl", "HIGHEST",   # run with highest privileges
        "/f",               # overwrite if exists
    ]
    code, out = run(cmd)
    if code == 0:
        print(f"Task '{TASK_NAME}' scheduled daily at {run_time}.")
        print(f"Python : {PYTHON_EXE}")
        print(f"Script : {BOT_SCRIPT}")
        print(f"\nVerify : schtasks /query /tn \"{TASK_NAME}\"")
        print(f"Run now: schtasks /run   /tn \"{TASK_NAME}\"")
        print(f"Delete : python setup_scheduler.py --delete")
    else:
        print(f"Failed to create task:\n{out}")
        sys.exit(1)


def delete_task():
    code, out = run(["schtasks", "/delete", "/tn", TASK_NAME, "/f"])
    if code == 0:
        print(f"Task '{TASK_NAME}' deleted.")
    else:
        print(f"Could not delete task:\n{out}")


def main():
    parser = argparse.ArgumentParser(description="Schedule Naukri Auto-Apply")
    parser.add_argument("--time",   default=None, help="Daily run time HH:MM (e.g. 09:00)")
    parser.add_argument("--delete", action="store_true", help="Remove the scheduled task")
    args = parser.parse_args()

    if args.delete:
        delete_task()
        return

    run_time = args.time
    if not run_time:
        run_time = input("Enter daily run time (HH:MM, 24-hour, e.g. 09:00): ").strip()
        if not run_time:
            run_time = "09:00"

    create_task(run_time)


if __name__ == "__main__":
    main()
