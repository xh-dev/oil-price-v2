#!/usr/bin/env python3
"""Trigger a Railway service redeploy using a Railway Project Token.

Each option can also come from an environment variable:
  RAILWAY_PROJECT_TOKEN (or RAILWAY_API_TOKEN), RAILWAY_SERVICE_ID, RAILWAY_ENVIRONMENT_ID

Examples:
  export RAILWAY_PROJECT_TOKEN=... RAILWAY_SERVICE_ID=... RAILWAY_ENVIRONMENT_ID=...
  ./scripts/redeploy-railway.py
  ./scripts/redeploy-railway.py --token T --service-id S --environment-id E
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

GRAPHQL_URL = "https://backboard.railway.com/graphql/v2"
MUTATION = """
mutation Redeploy($serviceId: String!, $environmentId: String!) {
  serviceInstanceRedeploy(serviceId: $serviceId, environmentId: $environmentId)
}
"""


def redeploy(token: str, service_id: str, environment_id: str, url: str = GRAPHQL_URL, timeout: float = 30) -> dict:
    """Send the redeploy mutation and return the decoded response. Raises RuntimeError on failure."""
    body = json.dumps({"query": MUTATION, "variables": {"serviceId": service_id, "environmentId": environment_id}}).encode()
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Project-Access-Token": token,
            "Content-Type": "application/json",
            "User-Agent": "oil-price-v2-redeploy/1.0",  # the default Python agent is blocked by Cloudflare
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')}") from e
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        raise RuntimeError(f"request failed: {e}") from e
    if data.get("errors"):
        raise RuntimeError(f"Railway returned errors: {json.dumps(data['errors'])}")
    return data


def main(argv: list[str] | None = None) -> int:
    env = os.environ.get
    parser = argparse.ArgumentParser(description="Trigger a Railway service redeploy.")
    parser.add_argument("-t", "--token", default=env("RAILWAY_PROJECT_TOKEN") or env("RAILWAY_API_TOKEN"),
                        help="Railway project token (default: $RAILWAY_PROJECT_TOKEN or $RAILWAY_API_TOKEN)")
    parser.add_argument("-s", "--service-id", default=env("RAILWAY_SERVICE_ID"), help="service id (default: $RAILWAY_SERVICE_ID)")
    parser.add_argument("-e", "--environment-id", default=env("RAILWAY_ENVIRONMENT_ID"), help="environment id (default: $RAILWAY_ENVIRONMENT_ID)")
    parser.add_argument("--url", default=GRAPHQL_URL, help="GraphQL endpoint (default: %(default)s)")
    parser.add_argument("--timeout", type=float, default=30, help="request timeout in seconds (default: %(default)s)")
    args = parser.parse_args(argv)

    missing = [flag for flag, value in (("--token", args.token), ("--service-id", args.service_id), ("--environment-id", args.environment_id)) if not value]
    if missing:
        parser.error(f"missing {', '.join(missing)} (or set the matching environment variable)")

    print(f"Triggering Railway redeploy (service: {args.service_id}, environment: {args.environment_id})...")
    try:
        data = redeploy(args.token, args.service_id, args.environment_id, url=args.url, timeout=args.timeout)
    except RuntimeError as e:
        print(f"error: redeploy failed: {e}", file=sys.stderr)
        return 1
    print(f"Response: {json.dumps(data)}")
    print("Successfully triggered redeploy on Railway!")
    return 0


if __name__ == "__main__":
    sys.exit(main())

