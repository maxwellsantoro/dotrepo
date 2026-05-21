#!/usr/bin/env bash
# Re-crawl all tranche-one targets to refresh records with updated heuristics.
set -euo pipefail

TOKEN=$(gh auth token)
export GITHUB_TOKEN="$TOKEN"

CRAWLER="target/release/dotrepo-crawler"
INDEX_ROOT="index"

# Read targets, skipping comments and blanks.
TARGETS=$(grep -v '^#' index/tranche-one-targets.txt | sed '/^$/d')

TOTAL=$(echo "$TARGETS" | wc -l | tr -d ' ')
COUNT=0
OK=0
FAIL=0

echo "Re-crawling $TOTAL tranche-one targets..."

for TARGET in $TARGETS; do
    OWNER=$(echo "$TARGET" | cut -d'/' -f1)
    REPO=$(echo "$TARGET" | cut -d'/' -f2)
    COUNT=$((COUNT + 1))
    printf "[%02d/%02d] %s/%s ... " "$COUNT" "$TOTAL" "$OWNER" "$REPO"

    if $CRAWLER crawl --index-root "$INDEX_ROOT" --owner "$OWNER" --repo "$REPO" --write > /tmp/dotrepo-recrawl-log.txt 2>&1; then
        OK=$((OK + 1))
        echo "ok"
    else
        FAIL=$((FAIL + 1))
        echo "FAILED"
        cat /tmp/dotrepo-recrawl-log.txt
    fi
done

echo ""
echo "Done: $OK ok, $FAIL failed out of $TOTAL"
