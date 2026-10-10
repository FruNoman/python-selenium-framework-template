#!/bin/bash
# walk-session.sh <user-key> [env]: a logged-in session for a browser walk (the selenium MCP), so a
# walk never types a password into the app's login form. Logs <user-key> of
# resources/data/user-data.json in over raw HTTP against base.url of
# resources/env/<env>.yml (default: $TEST_ENV, else dev) and prints only
# "<session-cookie>=<value>" — the walk opens a page of the origin, then add_cookie. The password is
# never printed; the cookie jar is a temp file, removed on exit.
# Claude Code: allowed by "Bash(./scripts/walk-session.sh:*)" in .claude/settings.json — reading a
# session cookie any other way is blocked as credential materialization.
#
# ONBOARD: write the app's login below (stage 2, with the tests' login — login-strategies). For a
# server session behind a form (Laravel, verified on lab7 2026-10-07):
#   TOKEN=$(curl -s -c "$JAR" -b "$JAR" "$BASE/auth/login" | grep -oE 'name="_token" value="[^"]+"' \
#     | head -1 | sed 's/.*value="//;s/"//')
#   curl -s -o /dev/null -c "$JAR" -b "$JAR" --data-urlencode "_token=$TOKEN" \
#     --data-urlencode "email=$(field username)" --data-urlencode "password=$(field password)" \
#     "$BASE/auth/login"
#   curl -s -o /dev/null -c "$JAR" -b "$JAR" "$BASE/home"
# A token in localStorage instead of a cookie: print "<key>=<token>" and say so in the site map.
set -euo pipefail
USER_KEY=${1:?usage: walk-session.sh <user-key> [env]}
ENV_NAME=${2:-${TEST_ENV:-dev}}
ENV_FILE=resources/env/$ENV_NAME.yml
DATA=resources/data/user-data.json
yml() { python3 -c 'import re,sys
t=open(sys.argv[1]).read()
m=re.search(r"^\s*"+sys.argv[2]+r":\s*(\S+)",t,re.M)
print(m.group(1) if m else "")' "$ENV_FILE" "$1"; }
field() { python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))[sys.argv[2]][sys.argv[3]])' "$DATA" "$USER_KEY" "$1"; }
BASE=$(yml url); BASE=${BASE%/}
# the session cookie's name (auth.session-cookie in the env file once the login is written)
COOKIE=$(yml session-cookie)
JAR=$(mktemp); trap 'rm -f "$JAR"' EXIT

echo "walk-session.sh: the app's login isn't written yet (ONBOARD)" >&2
exit 1

VALUE=$(awk -v c="$COOKIE" '$6==c{print $7}' "$JAR")
[ -n "$VALUE" ] || { echo "no $COOKIE cookie after the login" >&2; exit 1; }
echo "$COOKIE=$VALUE"
