#!/usr/bin/env bash
# Disposable, code-only cross-PR merge probe. Never touches DB, Storage or live services.
set -euo pipefail
export GIT_CONFIG_NOSYSTEM=1
git config user.name "NPDB synthetic merge probe"
git config user.email "npdb-qa@example.invalid"

# SHA pinning prevents a moving PR head from silently changing tested evidence.
declare -A HEADS=(
  [asset]="5bd0a7270c016627079d3c834eda9f7ed3dc5988"
  [index]="adca76625f728047208014b42d71a610c9309449"
  [cas]="df5f5666c9720e23cb09d57f5e8f780d870778e2"
  [wal]="76dfc5fcfe59ecde39b1ecea2755dc936586e010"
)
for id in asset index cas wal; do
  git fetch --no-tags --depth=80 origin "${HEADS[$id]}"
done
git config advice.detachedHead false
BASE="$(git rev-parse HEAD)"
printf 'Rehearsal base: %s\n' "$BASE"
failed=0
for id in asset index cas wal; do
  git reset --hard "$BASE" >/dev/null
  git clean -ffdq
  printf '\n=== Isolated merge: GPS/#39 plus %s ===\n' "$id"
  if git -c merge.conflictStyle=diff3 merge --no-edit --no-ff "${HEADS[$id]}" > /tmp/npdb-merge-result.txt 2>&1; then
    printf 'CLEAN MERGE %s\n' "$id"
  else
    failed=1
    printf 'CONFLICT %s\n' "$id"
    git diff --name-only --diff-filter=U
    git merge --abort || true
  fi
done
git reset --hard "$BASE" >/dev/null
git clean -ffdq
printf '\n=== Combined ordered merge ===\n'
for id in asset index cas wal; do
  printf 'Merging %s\n' "$id"
  if git merge --no-edit --no-ff "${HEADS[$id]}" >/tmp/npdb-merge-result.txt 2>&1; then
    printf 'CLEAN %s\n' "$id"
  else
    failed=1
    printf 'COMBINED CONFLICT %s\n' "$id"
    git diff --name-only --diff-filter=U
    break
  fi
done
if (( failed != 0 )); then
  echo "Cross-PR integration needs explicit resolution; DO NOT merge to QA/main."
  exit 1
fi
echo "Combined code merge clean; separate full-suite/tests/independent review still mandatory."
