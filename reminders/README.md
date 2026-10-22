# Ticket Alert Reminders

Automated Redmine ticket forecast reminder generator for QE Tools.

Monitors three Redmine queries on `progress.opensuse.org`:
- **#651**: Due Date forecast (alerts when due date arrives)
- **#1016**: SLO High forecast (alerts if high-priority tickets are inactive > 7 days)
- **#1019**: SLO Normal forecast (alerts if normal-priority tickets are inactive > 30 days)

---

## Slack Workflow Builder Integration

The script sends a JSON payload with separate variables for each alert category and the calculated dates:

| Webhook Variable Key | Content | Example |
|---|---|---|
| `weekday` | Capitalized weekday name of target date | `Monday` |
| `target_weekday` | Alias for `weekday` | `Monday` |
| `previous_workday` | Previous business day (skips weekend) | `Friday` |
| `prev_workday` | Alias for `previous_workday` | `Friday` |
| `target_date` | Date string | `2026-10-26` |
| `due_date_slo_high` | List of tickets hitting Due Date & SLO High alerts | `- (Feedback) ...` or `✅` |
| `due_date` | List of tickets hitting Due Date alerts | `- (In Progress) ...` or `✅` |
| `slo_high` | List of tickets hitting SLO High alerts | `- (In Progress) ...` or `✅` |
| `due_date_slo_normal`| List of tickets hitting Due Date & SLO Normal | `✅` |
| `slo_normal` | List of tickets hitting SLO Normal | `✅` |

### Empty List Behavior
If a category has no tickets, its variable value is set to **`🔸✅ No tickets right now`**.

### Ticket Item Format
```text
🔸 (<STATUS>) <SUBJECT> - @<SLACK_HANDLE>
    🔸 <TICKET_URL>
```

---

## Configuration

| Variable | Type | Description |
|---|---|---|
| `REDMINE_API_KEY` | Secret | Required. Redmine API key for progress.opensuse.org. |
| `WEBHOOK_URL` | Secret | Required in CI. Slack Workflow Builder Webhook URL. |
| `SLACK_USER_MAPPING` | Variable | Optional. Redmine username to Slack User ID or handle mapping. |

### Team Name Mapping (`SLACK_USER_MAPPING`)

In GitHub: **Settings > Secrets and variables > Actions > Variables > New repository variable**.

Map Redmine usernames to human-readable names or Slack usernames:

```yaml
user_login1: First Last
user_login2: username
```

- Each ticket assignee will be rendered cleanly as `- (Status) Subject - @First Last`.
- If an assignee is unmapped, it falls back to `@here`.

---

## Local Usage

```bash
REDMINE_API_KEY="your_api_key" python3 reminders/generate_reminders.py --dry-run
```
