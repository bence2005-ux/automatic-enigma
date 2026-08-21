# Daily Discord Server Status Updater

Automatically keeps a webhook embed up to date once a day, with zero servers
to maintain — it runs on GitHub's free scheduled Actions runners.

## Setup

### 1. Create a repo
Create a new (can be private) GitHub repo and add these two files, keeping
the same folder structure:

```
update_status.py
.github/workflows/daily-update.yml
```

### 2. Create a Discord webhook
In your Discord channel: **Edit Channel → Integrations → Webhooks → New Webhook**.
Copy the Webhook URL.

### 3. Add secrets to your repo
Go to **Settings → Secrets and variables → Actions → New repository secret**
and add:

- `WEBHOOK_URL` — the webhook URL you copied
- `MESSAGE_ID` — leave this **empty/unset** for the very first run

### 4. First run
Go to the **Actions** tab → "Daily Server Status Update" → **Run workflow**
(manual trigger). This sends the first message and prints something like:

```
::notice::NEW_MESSAGE_ID=1234567890123456789
```

Copy that ID, then go back to your repo secrets and **add/update**
`MESSAGE_ID` with that value.

### 5. Done
From now on, the workflow runs automatically every day at the cron time set
in `daily-update.yml` (default 06:00 UTC) and **edits that same message in
place** — no manual work needed.

## Customizing

Open `update_status.py` and edit the `REGIONS` dict at the top:

- `tz`: any valid IANA timezone name (e.g. `"America/Los_Angeles"`,
  `"Europe/London"`, `"Asia/Seoul"`)
- `ansi_color`: ANSI color code used inside the ```ansi block
  (`31`=red, `32`=green, `33`=yellow, `34`=blue, `35`=magenta, `36`=cyan,
  `37`=white/gray)

Also adjust:
- `DAILY_RESET_HOUR` — local hour (0–23) each region's daily reset happens
- `WEEKLY_RESET_WEEKDAY` / `WEEKLY_RESET_HOUR` — when the weekly reset happens
- `MEMBER_COUNT` — static text, update manually or wire up to a real member
  count if you have a bot token with server access

## Edit vs. delete+resend

Default mode is `edit`, which updates the existing message in place (keeps
it in the same spot in the channel history). If you'd rather have it
reappear at the bottom of the channel each day, change `MODE: edit` to
`MODE: delete_resend` in the workflow file — but note this loses pins and
changes the message ID each day, so you'd need to add a step to persist the
new ID automatically (e.g. writing it back to a repo secret via the GitHub
CLI, or storing it in a tiny gist/DB instead of a secret).
