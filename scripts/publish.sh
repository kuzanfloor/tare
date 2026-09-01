#!/usr/bin/env bash
# Refresh the reading and publish it. Runs on the VPS so the x402 key never
# reaches GitHub. Verifies the push LANDED rather than trusting git's exit code
# — a publisher that reports success while the page stays stale is the failure
# mode this whole project argues against.
set -uo pipefail

# Derived, not hardcoded: an absolute home path in a public repo is a leak,
# and the pre-commit hook rejects it — correctly.
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 1

export PATH="/usr/bin:/bin:$PATH"
export TARE_BUY_INFERENCE="${TARE_BUY_INFERENCE:-1}"

# Take whatever the remote has first; the reading is regenerated either way and
# .gitattributes resolves the generated files without a conflict.
GIT_SSH_COMMAND="ssh -o ConnectTimeout=20 -o BatchMode=yes" \
  git fetch -q origin main 2>/dev/null || true
git rebase -q FETCH_HEAD >/dev/null 2>&1 || {
  git checkout --ours docs/snapshot.json 2>/dev/null
  # SOLO docs/. `git add -A` metteva in stage l'INTERO albero di lavoro, e il
  # commit successivo lo pubblicava sotto "chore: refresh reading" su un repo
  # PUBBLICO. Successo l'01/09/2026: una modifica al client di pagamento, in
  # corso di scrittura, e' finita spinta con quel messaggio. Qualunque lavoro non
  # finito presente sulla macchina sarebbe uscito allo stesso modo.
  git add docs/ >/dev/null 2>&1
  GIT_EDITOR=true git rebase --continue >/dev/null 2>&1 || git rebase --abort
}

PYTHONPATH=. "$REPO/venv/bin/python" "$REPO/scripts/refresh_snapshot.py" || {
  echo "refresh failed" >&2; exit 1; }

git add docs/ >/dev/null 2>&1
if git diff --cached --quiet; then
  echo "reading unchanged — nothing to publish"
  exit 0
fi
git commit -q -m "chore: refresh reading" || { echo "commit failed" >&2; exit 1; }

PUSHED=0
for attempt in 1 2 3; do
  if GIT_SSH_COMMAND="ssh -o ConnectTimeout=20 -o BatchMode=yes" \
     git push -q origin HEAD:main 2>/dev/null; then PUSHED=1; break; fi
  sleep $((attempt * 10))
done

# Verify the effect: does the remote actually carry our commit?
LOCAL=$(git rev-parse HEAD)
REMOTE=$(GIT_SSH_COMMAND="ssh -o ConnectTimeout=20 -o BatchMode=yes" \
         git ls-remote origin main 2>/dev/null | cut -f1)
if [ "$LOCAL" != "$REMOTE" ]; then
  echo "push did not land: local ${LOCAL:0:7} remote ${REMOTE:0:7} (pushed=$PUSHED)" >&2
  exit 1
fi

echo "published ${LOCAL:0:7}"
