# Live Desk
Private TikTok Live reports with a Shopify-inspired dashboard. Tracks host, session times, GMV in MYR, views, history and CSV exports. Daily GMV/views line charts support 7 or 30 days.

## Accounts and privacy
On first start the server generates a manager account. Read `/data/manager-access.txt` inside the container for its username and password. Keep these credentials private. The manager creates individual host accounts in the dashboard; each generated host password is displayed once. New passwords contain 12 easy-to-read random letters and digits. Existing passwords remain valid.

Hosts can only read and export their own records. Ownership is enforced on the server and comes from the signed-in account. Passwords use salted scrypt hashes; sessions use revocable, 12-hour HttpOnly cookies. Serve behind HTTPS for deployment.

Set `ADMIN_CAN_VIEW_ALL=true` to let the manager view all reports and filter charts by host. Existing reports stay in the database and remain manager-only until explicitly assigned to a host. Name matches never grant access automatically.

## Synology deployment
Upload Dockerfile, server.py, bootstrap.py, compose.yaml and the public folder to a Container Manager project directory. Build the project with compose.yaml. The app listens on localhost port 8088; configure an HTTPS reverse proxy to that port. Preserve the live-records volume during updates: it contains the database and manager access file. Back up that volume regularly.

## Local development
Use Python 3.12+ and run `python server.py`; open http://127.0.0.1:8000. The local manager access file is in data/. To test: `python -m unittest discover -s tests`.

Hosts and managers can choose Change password in the header. They must enter their current password and confirm a new password (12–128 characters). A successful change signs out all devices. The manager access file contains the initial password only.

## Edit session records
Each host can choose Edit on their own session, update its times, GMV, views or notes, and save changes. Ownership is enforced by the server. Manager can edit only the manager account's own sessions. No delete control is provided.

## Email password recovery
Configure SMTP_HOST, SMTP_PORT (587 by default), SMTP_TLS (starttls or ssl), SMTP_FROM, SMTP_USER, SMTP_PASSWORD and PUBLIC_URL=https://sampin-live-host.synology.me/ in the NAS project environment. Keep SMTP credentials out of GitHub. SMTP always uses TLS and certificate verification.

Each host and manager must open Recovery email, enter an email and current password, then confirm the verification link received by email. Existing accounts have no recovery email until this step is completed. Forgot password sends a single-use reset link to the verified email. Links expire after 20 minutes; successful resets revoke all sign-ins. Tokens are hashed in the database and sent in URL fragments so they do not appear in server request logs. Unknown email addresses receive the same response. Without SMTP configuration the form reports that email recovery is unavailable.

## Private host rank
Hosts see only their own all-time GMV rank. Rankings include non-manager accounts with at least one recorded session. Equal GMV totals share a rank (1, 1, 3). Unassigned legacy records and manager sessions are excluded. No other host names, totals, or leaderboard rows are returned by the rank API. Rank refreshes on sign-in, page reload and after saving or editing a session.
