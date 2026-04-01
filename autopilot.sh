#!/bin/bash
# BAKY Autopilot — Simple loop that runs until no open MVP issues remain.
# Each iteration: fresh Claude process → build one issue → exit → repeat.
#
# Usage: ./autopilot.sh
# Stop:  Ctrl+C

set -e

REPO="robert197/baky"
PROMPT_FILE=".ralph/PROMPT.md"
LOG_DIR=".ralph/logs"
mkdir -p "$LOG_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

iteration=0

while true; do
    iteration=$((iteration + 1))
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    log_file="$LOG_DIR/iteration-${iteration}-$(date '+%Y%m%d-%H%M%S').log"

    # Check how many MVP issues remain
    remaining=$(gh issue list -R "$REPO" --milestone "MVP (Weeks 1-4)" --state open --json number -q 'length' 2>/dev/null || echo "?")

    if [ "$remaining" = "0" ]; then
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${GREEN}  MVP COMPLETE — All issues shipped!${NC}"
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        exit 0
    fi

    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  Iteration #${iteration} — ${timestamp}${NC}"
    echo -e "${BLUE}  Open MVP issues: ${remaining}${NC}"
    echo -e "${BLUE}  Log: ${log_file}${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # Run Claude with the prompt — fresh process, no session continuity
    claude --print \
        --dangerously-skip-permissions \
        --prompt-file "$PROMPT_FILE" \
        2>&1 | tee "$log_file"

    exit_code=$?

    if [ $exit_code -ne 0 ]; then
        echo -e "${YELLOW}  Claude exited with code ${exit_code}. Waiting 30s before retry...${NC}"
        sleep 30
    fi

    # Brief pause between iterations
    echo -e "${GREEN}  Iteration #${iteration} finished. Starting next in 5s...${NC}"
    sleep 5
done
