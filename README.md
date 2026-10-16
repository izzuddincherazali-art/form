# Live Desk

A Shopify-inspired TikTok Live reporting dashboard. Hosts record their name, start/end date and time, sales GMV in MYR, views, and optional notes. Includes all-time totals, host search and CSV export. No Shopify or TikTok account integration is required; results are entered manually.

## Run locally

Requires Python 3.10+ (standard library only).

```sh
python3 server.py
```

Open http://127.0.0.1:8000. The SQLite database is created at `data/sessions.sqlite3`. Reloading or restarting preserves records. All session times are Malaysia local time (UTC+8). GMV is stored as integer cents.

## Host for your team

Run on a Python-capable server with a persistent disk. GitHub stores the source code; GitHub Pages cannot run this database server.

```sh
export HOST=0.0.0.0
export PORT=8000
export DATABASE_PATH=/your/persistent/disk/sessions.sqlite3
export APP_PASSWORD='replace-with-a-long-private-team-password'
python3 server.py
```

Use an HTTPS reverse proxy in front of this server, restrict direct access to the backend port, and share the team password privately. A password of at least 12 characters is enforced when binding beyond localhost. Enter it with Team access in the dashboard. It stays in sessionStorage for the browser tab. This first version uses a shared team password: all authorized hosts can view all records. It does not provide separate admin accounts, individual user attribution, edit/delete controls, or automated TikTok imports.

Back up the SQLite file regularly using SQLite's backup API or while the service is stopped. Never commit databases or passwords to GitHub. Keep the database on persistent storage; ephemeral hosting disks lose records on redeploy.

## Validation

```sh
python3 -m unittest discover -s tests
```
