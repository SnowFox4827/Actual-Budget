#!/usr/bin/env python3
"""Actual Budget - backup sidecar.

Creates dated .tar.gz archives of the budget data directory, prunes old
ones, and loops either on an interval or daily at a fixed time (BACKUP_AT).

Environment (set in docker-compose.yml from .env):
  DATA_DIR                budget data to back up (read-only mount, default /data)
  BACKUP_DIR              where archives go (default /backups)
  BACKUP_RETENTION_DAYS   prune archives older than this (default 30)
  BACKUP_PREFIX           archive filename prefix (default actual-backup)
  BACKUP_INTERVAL_H       run every N hours (default 24), ignored if BACKUP_AT set
  BACKUP_AT               run daily at "HH:MM" 24h clock (default "" = interval mode)
  RUN_ONCE                "1" = run one backup and exit
"""
import hashlib
import os
import sys
import tarfile
import time
from datetime import datetime, timedelta, timezone

DATA_DIR = os.environ.get("DATA_DIR", "/data")
BACKUP_DIR = os.environ.get("BACKUP_DIR", "/backups")
RETENTION_DAYS = int(os.environ.get("BACKUP_RETENTION_DAYS", "30"))
PREFIX = os.environ.get("BACKUP_PREFIX", "actual-backup")


def log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def run_backup() -> bool:
    log("Starting backup...")
    if not os.path.isdir(DATA_DIR) or not os.listdir(DATA_DIR):
        log(f"Warning: data directory {DATA_DIR} is empty or missing. Skipping.")
        return False

    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive = os.path.join(BACKUP_DIR, f"{PREFIX}-{stamp}.tar.gz")

    try:
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(DATA_DIR, arcname="data")
        size_mb = os.path.getsize(archive) / 1024 / 1024
        log(f"Archive written: {archive} ({size_mb:.1f} MB)")
    except Exception as e:
        log(f"Backup error: {e}")
        return False

    # SHA-256 checksum beside the archive, for integrity verification later
    try:
        h = hashlib.sha256()
        with open(archive, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        with open(archive + ".sha256", "w") as cf:
            cf.write(f"{h.hexdigest()}  {os.path.basename(archive)}\n")
        log("Checksum recorded.")
    except Exception as e:
        log(f"Checksum error: {e}")

    # Retention pruning (archives older than the cutoff, checksums included)
    cutoff = time.time() - RETENTION_DAYS * 86400
    pruned = 0
    try:
        for name in os.listdir(BACKUP_DIR):
            if not (name.startswith(PREFIX + "-") and (name.endswith(".tar.gz") or name.endswith(".sha256"))):
                continue
            path = os.path.join(BACKUP_DIR, name)
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
                pruned += 1
        if pruned:
            log(f"Pruned {pruned} old archive(s) (>{RETENTION_DAYS} days).")
    except Exception as e:
        log(f"Pruning error: {e}")

    log("Backup finished successfully.")
    return True


def seconds_until(hhmm: str) -> float:
    """Seconds until the next occurrence of HH:MM."""
    hh, mm = map(int, hhmm.split(":"))
    now = datetime.now()
    target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def main() -> None:
    backup_at = os.environ.get("BACKUP_AT", "").strip()
    interval_h = float(os.environ.get("BACKUP_INTERVAL_H", "24"))

    if os.environ.get("RUN_ONCE") == "1" or "--once" in sys.argv:
        sys.exit(0 if run_backup() else 1)

    if backup_at:
        log(f"Backup daemon starting: daily at {backup_at}, retention {RETENTION_DAYS} days.")
        run_backup()  # immediate first backup so there's always at least one
        while True:
            wait = seconds_until(backup_at)
            log(f"Next backup in {wait / 3600:.1f}h.")
            time.sleep(max(wait, 1))
            run_backup()
    else:
        log(f"Backup daemon starting: every {interval_h:g}h, retention {RETENTION_DAYS} days.")
        while True:
            run_backup()
            time.sleep(interval_h * 3600)


if __name__ == "__main__":
    main()
