#!/usr/bin/env python3
"""Submit a local file to one packaged WEGIS WorkBuddy skill."""

import json
import os
import sys
import time
from pathlib import Path

import requests


SKILL_KEY = "flood-recognition-wegis"
GATEWAY_URL = os.getenv("WEGIS_GATEWAY_URL", "https://ai.wegis.com.cn/workbuddy").rstrip("/")


def main() -> int:
    arguments = [argument for argument in sys.argv[1:] if argument != "--wait"]
    wait_for_result = "--wait" in sys.argv[1:]
    if not arguments:
        print("Usage: python submit_job.py <input-file> [cusParams-json] [--wait]", file=sys.stderr)
        return 2
    source = Path(arguments[0]).expanduser()
    if not source.is_file():
        print(f"File not found: {source}", file=sys.stderr)
        return 2
    try:
        params = json.loads(arguments[1]) if len(arguments) > 1 else {}
    except json.JSONDecodeError as exc:
        print(f"Invalid cusParams JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(params, dict):
        print("cusParams must be a JSON object", file=sys.stderr)
        return 2

    headers = {}
    api_key = os.getenv("WEGIS_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key
    with source.open("rb") as stream:
        response = requests.post(
            f"{GATEWAY_URL}/v1/jobs/{SKILL_KEY}",
            headers=headers,
            data={"params": json.dumps(params, ensure_ascii=False)},
            files={"file": (source.name, stream)},
            timeout=(30, 3600),
        )
    try:
        payload = response.json()
    except ValueError:
        print(response.text, file=sys.stderr)
        return 1
    if not response.ok or not wait_for_result:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if response.ok else 1

    task_id = payload.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1

    max_wait_seconds = int(os.getenv("WEGIS_MAX_WAIT_SECONDS", "3600"))
    deadline = time.monotonic() + max_wait_seconds
    while time.monotonic() < deadline:
        status_response = requests.get(
            f"{GATEWAY_URL}/v1/jobs/{task_id}", headers=headers, timeout=(30, 120)
        )
        try:
            status_payload = status_response.json()
        except ValueError:
            print(status_response.text, file=sys.stderr)
            return 1
        task = ((status_payload.get("task") or {}).get("data") or {}).get("vo") or {}
        status = str(task.get("status", ""))
        if status == "2":
            print(json.dumps(status_payload, ensure_ascii=False, indent=2))
            return 0
        if status in {"3", "4", "5"}:
            print(json.dumps(status_payload, ensure_ascii=False, indent=2))
            return 1
        time.sleep(5)

    print(f"Task {task_id} did not finish within {max_wait_seconds} seconds", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
