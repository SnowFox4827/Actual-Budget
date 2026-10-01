# Actual Budget — Local Self-Hosted Setup

## About

[Actual Budget](https://actualbudget.org/) is a free, open-source, privacy-focused
budgeting app built on the zero-based envelope method: you only budget money you
actually have on hand, so your budget always reflects reality (very similar to YNAB).

- **Local-first** — data lives on your server and devices; nothing goes to the cloud
- **Multi-device sync** — built-in sync server; use the same budget from any device on your network
- **End-to-end encryption** — optional, for extra safety
- **Bank sync** — optional, via SimpleFIN (US/Canada) or goCardless (EU/UK)
- **Importing** — QIF, OFX, QFX, CAMT.053, CSV, plus YNAB4 / nYNAB importers
- **Reports** — net worth, cash flow, and a custom report builder

This setup is for **local network use only** (no public internet exposure, no HTTPS proxy).

## Files

- `docker-compose.yml` — Actual, with data in `./actual-data`. The host port comes from
  `APP_PORT` in `.env` (default 5006). Includes an optional backup sidecar service.
- `backup.py` + `Dockerfile.backup` — the backup job the sidecar runs
- `.env.example` — settings file: copy it to `.env` and edit

## Environment file (.env)

```bash
cp .env.example .env
```

Available settings:

| Variable | Default | Meaning |
|---|---|---|
| `APP_PORT` | `5006` | Host port for the web app |
| `BACKUP_DIR` | `./backups` | Where backup archives are written |
| `BACKUP_RETENTION_DAYS` | `30` | Delete archives older than this |
| `BACKUP_PREFIX` | `actual-backup` | Filename prefix for archives |
| `BACKUP_AT` | `22:30` | Daily backup time, `HH:MM` 24h clock |
| `TZ` | `UTC` | Container timezone — makes `BACKUP_AT` mean your local time (e.g. `America/Chicago` for 10:30 pm) |

## Requirements

- Docker Engine 20.10+ and Docker Compose v2 (`docker compose` command)
- Port 5006 free on the host (or whatever `APP_PORT` is set to in `.env`)

## Run it

1. Put `docker-compose.yml`, `Dockerfile.backup`, `backup.py` and `.env.example`
   in an empty folder, then from that folder:

   ```bash
   cp .env.example .env
   ```

   Docker Compose ignores dotfiles when copying a project around, so make sure
   `.env` comes along — don't rename it.

2. Start the app and the backup sidecar:

   ```bash
   docker compose up -d
   ```

3. Open **http://<your-server-ip>:<APP_PORT>** from any device on your network
   (e.g. `http://192.168.1.10:5006`) and create your budget.

4. Changing the port: edit `APP_PORT` in `.env`, then restart:

   ```bash
   docker compose up -d
   ```

   The app is then at `http://<your-server-ip>:<APP_PORT>`.

## Keeping it running

The containers restart automatically on reboot (`restart: unless-stopped`).

## Updates

```bash
docker compose pull
docker compose up -d
```

Old image cleanup (optional): `docker image prune`

## Backups

Everything lives in the `./actual-data` folder next to the compose file — budgets,
preferences, everything.

The backup runs as a sidecar container (`actual-backup`) built from
`Dockerfile.backup` (python:3.11-alpine running `backup.py`) that:

- mounts `./actual-data` **read-only** — it can never damage the live budget
- writes dated archives to `BACKUP_DIR` (default `./backups`), each with a
  matching `.sha256` checksum file
- runs immediately at start, then daily at `BACKUP_AT` (default `"22:30"` = 10:30 pm)
- can write to a NAS mount: set `BACKUP_DIR` to the host mount path, e.g.
  `/srv/dev-disk-by-uuid-XXXX-XXXX/Backups/ActualBudget`. Make sure the share is
  mounted before `docker compose up`, otherwise archives silently land in an
  empty local folder
- prunes archives older than `BACKUP_RETENTION_DAYS`

Check its status/logs:

```bash
docker compose ps
docker compose logs -f backup
```

Restore: stop the container, extract the archive over `actual-data/`, start again.

Manual one-off backup from the sidecar (optional):

```bash
docker compose exec backup python /app/backup.py --once
```

## Timezone

`BACKUP_AT` is interpreted in the container's timezone, which defaults to UTC.
Set `TZ` in `.env` (e.g. `TZ=America/Chicago`) so 22:30 means your local 10:30 pm.

## Bank sync (optional)

1. Sign up for [SimpleFIN](https://bridge.simplefin.org/) (US/Canada)
   or goCardless (EU/UK).
2. In the Actual web app, go to the server settings and paste your access key.

## Troubleshooting

- Status/logs: `docker compose ps`, `docker compose logs -f actual_server backup`
- Health check: `curl http://localhost:$APP_PORT/health` should return a 200
- Port busy? Change `APP_PORT` in `.env`, then `docker compose up -d`

## Firewall note

Only devices on your local network can reach it as long as your router does not
port-forward `APP_PORT` (default 5006) to the internet. Don't set up forwarding unless you also add HTTPS.
