#!/usr/bin/env bash
# Usage: ./refresh.sh <image_name>
image_name=$1

# Gotify notification settings. Fill them in and uncomment; while unset, no notification is sent.
# GOTIFY_URL="https://gotify.example.com"   # base address of your Gotify server
# GOTIFY_TOKEN="<application token>"        # token of the Gotify application

notify() {  # notify <title> <message> [priority]
  [[ -n "${GOTIFY_URL:-}" && -n "${GOTIFY_TOKEN:-}" ]] || return 0
  curl -fsS -o /dev/null -X POST "${GOTIFY_URL%/}/message?token=${GOTIFY_TOKEN}" \
    -F "title=$1" -F "message=$2" -F "priority=${3:-5}" \
    || echo "warning: could not send the Gotify notification" >&2
}

# step <name> <command...>: run a command, notify about the result, stop at the first failure.
step() {
  local name=$1; shift
  notify "oil-price-v2: $name" "started"
  if "$@"; then
    notify "oil-price-v2: $name" "done"
  else
    local code=$?
    notify "oil-price-v2: $name FAILED" "exit code $code" 8
    exit "$code"
  fi
}

step fetch          oil-price-v2 fetch
step decode         oil-price-v2 decode --provider ollama --model qwen3.6:35b-mlx-cust
step gen-html       oil-price-v2 gen-html
step gen-dockerfile oil-price-v2 gen-dockerfile --force
step docker-build   sudo docker build -t "$image_name" .
step docker-push    sudo docker push "$image_name"

notify "oil-price-v2: refresh finished" "image $image_name pushed"
