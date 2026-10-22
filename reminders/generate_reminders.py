#!/usr/bin/env python3
import os
import sys
import json
import argparse
from datetime import datetime, date, timedelta
import requests

REDMINE_URL = "https://progress.opensuse.org"
WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

def parse_user_mapping(raw_str):
    """Parses a simple 'username: slack_handle_or_id' string into a dictionary."""
    if not raw_str:
        return {}
    raw_str = raw_str.strip()
    if raw_str.startswith("{"):
        try:
            return {k: str(v).strip() for k, v in json.loads(raw_str).items()}
        except Exception:
            pass
    mapping = {}
    for line in raw_str.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        delimiter = ":" if ":" in line else "=" if "=" in line else None
        if delimiter:
            k, v = line.split(delimiter, 1)
            mapping[k.strip()] = v.strip()
    return mapping

def load_slack_mapping(mapping_file="slack_mapping.json"):
    """Loads mapping from SLACK_USER_MAPPING env var, or optional local file."""
    env_mapping = os.environ.get("SLACK_USER_MAPPING")
    if env_mapping:
        return parse_user_mapping(env_mapping)
    for path in [mapping_file, os.path.join(os.path.dirname(__file__), mapping_file)]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return {k: str(v).strip() for k, v in json.load(f).items()}
            except Exception:
                pass
    return {}

def format_mention(handle):
    """
    Formats a user handle for clean text display in Slack Workflow Builder:
    - Avoids '<' and '>' because Workflow Builder prints them literally.
    - Returns '@handle' or '@here'.
    """
    if not handle:
        return "@here"
    handle = handle.strip()
    if handle in ("here", "@here", "<!here>"):
        return "@here"
    clean = handle.replace("<", "").replace(">", "").replace("@", "").replace("!", "").strip()
    if not clean:
        return "@here"
    return f"@{clean}"

def get_next_weekday(weekday_name, base_date=None):
    if base_date is None:
        base_date = date.today()
    target = WEEKDAYS[weekday_name.lower()]
    days_ahead = target - base_date.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return base_date + timedelta(days=days_ahead)

def get_previous_workday(target_date):
    """Calculates the previous workday (skipping weekends)."""
    if target_date.weekday() == 0:    # Monday -> Friday
        prev_date = target_date - timedelta(days=3)
    elif target_date.weekday() == 6:  # Sunday -> Friday
        prev_date = target_date - timedelta(days=2)
    else:
        prev_date = target_date - timedelta(days=1)
    return prev_date.strftime("%A")

def fetch_issues(query_id, api_key):
    headers = {"X-Redmine-API-Key": api_key}
    url = f"{REDMINE_URL}/issues.json"
    offset, limit = 0, 100
    issues = []
    while True:
        resp = requests.get(url, headers=headers, params={"query_id": query_id, "offset": offset, "limit": limit}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("issues", [])
        issues.extend(batch)
        offset += len(batch)
        if offset >= data.get("total_count", 0) or not batch:
            break
    return issues

def evaluate_tickets(q651, q1016, q1019, target_date):
    tracked = {}
    slo_high_thresh = target_date - timedelta(days=7)
    slo_norm_thresh = target_date - timedelta(days=30)

    for issue in q651:
        if issue.get("due_date"):
            due_d = datetime.strptime(issue["due_date"], "%Y-%m-%d").date()
            if due_d <= target_date:
                tracked.setdefault(issue["id"], {"issue": issue, "reasons": set()})["reasons"].add("due")

    for issue in q1016:
        if issue.get("updated_on"):
            upd_d = datetime.fromisoformat(issue["updated_on"].replace("Z", "+00:00")).date()
            if upd_d <= slo_high_thresh:
                tracked.setdefault(issue["id"], {"issue": issue, "reasons": set()})["reasons"].add("slo_high")

    for issue in q1019:
        if issue.get("updated_on"):
            upd_d = datetime.fromisoformat(issue["updated_on"].replace("Z", "+00:00")).date()
            if upd_d <= slo_norm_thresh:
                tracked.setdefault(issue["id"], {"issue": issue, "reasons": set()})["reasons"].add("slo_norm")

    groups = {
        "Due date & SLO high": [],
        "Due date & SLO normal": [],
        "Due date": [],
        "SLO high": [],
        "SLO normal": []
    }
    for item in tracked.values():
        issue, reasons = item["issue"], item["reasons"]
        if "due" in reasons and "slo_high" in reasons:
            groups["Due date & SLO high"].append(issue)
        elif "due" in reasons and "slo_norm" in reasons:
            groups["Due date & SLO normal"].append(issue)
        elif "due" in reasons:
            groups["Due date"].append(issue)
        elif "slo_high" in reasons:
            groups["SLO high"].append(issue)
        elif "slo_norm" in reasons:
            groups["SLO normal"].append(issue)

    for g in groups.values():
        g.sort(key=lambda x: x.get("priority", {}).get("id", 0), reverse=True)
    return groups

def format_ticket_list(issues, mapping):
    """
    Formats a list of tickets:
    🔸 (<STATUS>) <SUBJECT> - <MENTION>
        🔸 <TICKET_URL>
    Returns '🔸✅ No tickets right now' if the list is empty.
    """
    if not issues:
        return "🔸✅ No tickets right now"

    lines = []
    for issue in issues:
        status = issue.get("status", {}).get("name", "Unknown")
        subject = issue.get("subject", "").strip()
        ticket_url = f"{REDMINE_URL}/issues/{issue['id']}"

        # Resolve assignee handle; fallback to 'here'
        assigned_to = issue.get("assigned_to")
        username = assigned_to.get("name") if assigned_to else None
        handle = mapping.get(username) if username else None
        mention = format_mention(handle)

        lines.append(f"🔸 ({status}) {subject} - {mention}")
        lines.append(f"    🔸 {ticket_url}")
    return "\n".join(lines)

def build_payload(groups, mapping, target_date):
    """Builds the JSON payload with separate variables for Slack Workflow Builder."""
    weekday_name = target_date.strftime("%A")
    prev_workday = get_previous_workday(target_date)
    return {
        "weekday": weekday_name,
        "target_weekday": weekday_name,
        "previous_workday": prev_workday,
        "prev_workday": prev_workday,
        "target_date": target_date.strftime("%Y-%m-%d"),
        "due_date_slo_high": format_ticket_list(groups["Due date & SLO high"], mapping),
        "due_date": format_ticket_list(groups["Due date"], mapping),
        "slo_high": format_ticket_list(groups["SLO high"], mapping),
        "due_date_slo_normal": format_ticket_list(groups["Due date & SLO normal"], mapping),
        "slo_normal": format_ticket_list(groups["SLO normal"], mapping),
    }

def main():
    parser = argparse.ArgumentParser(description="Generate Redmine ticket alert reminders.")
    parser.add_argument("--target-weekday", choices=list(WEEKDAYS.keys()), default="monday")
    parser.add_argument("--target-date", type=str, help="Explicit target date YYYY-MM-DD")
    parser.add_argument("--format", default="slack", help="Output format (accepted for backwards compatibility)")
    parser.add_argument("--dry-run", action="store_true", help="Print payload without sending to webhook")
    parser.add_argument("--dry-run-file", type=str, help="Test with mock query JSON file")
    args = parser.parse_args()

    target_date = datetime.strptime(args.target_date, "%Y-%m-%d").date() if args.target_date else get_next_weekday(args.target_weekday)
    mapping = load_slack_mapping()

    if args.dry_run_file:
        with open(args.dry_run_file, "r", encoding="utf-8") as f:
            mock = json.load(f)
        q651, q1016, q1019 = mock.get("651", []), mock.get("1016", []), mock.get("1019", [])
    else:
        api_key = os.environ.get("REDMINE_API_KEY")
        if not api_key:
            print("Error: REDMINE_API_KEY environment variable is not set.", file=sys.stderr)
            sys.exit(1)
        q651 = fetch_issues(651, api_key)
        q1016 = fetch_issues(1016, api_key)
        q1019 = fetch_issues(1019, api_key)

    groups = evaluate_tickets(q651, q1016, q1019, target_date)
    payload = build_payload(groups, mapping, target_date)

    print(json.dumps(payload, indent=2, ensure_ascii=False))

    webhook_url = os.environ.get("WEBHOOK_URL") or os.environ.get("SLACK_WEBHOOK_URL")
    if webhook_url and not args.dry_run:
        resp = requests.post(webhook_url, json=payload, timeout=15)
        resp.raise_for_status()

if __name__ == "__main__":
    main()
