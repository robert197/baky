#!/bin/bash
# BAKY Autopilot — Simple loop that runs until no open MVP issues remain.
# Each iteration: fresh Claude process → build one issue → exit → repeat.
#
# Usage:
#   ./autopilot.sh              # Normal mode (logs to file, summary to terminal)
#   ./autopilot.sh --verbose    # Verbose mode (full Claude output streams to terminal)
#   ./autopilot.sh --tail       # Tail the latest log in a second terminal
#
# Stop: Ctrl+C

set -e

REPO="robert197/baky"
PROMPT_FILE=".ralph/PROMPT.md"
LOG_DIR=".ralph/logs"
mkdir -p "$LOG_DIR"

# Parse flags
VERBOSE=false
TAIL_MODE=false
for arg in "$@"; do
    case $arg in
        --verbose|-v) VERBOSE=true ;;
        --tail|-t) TAIL_MODE=true ;;
    esac
done

# Tail mode — just follow the latest log
if [ "$TAIL_MODE" = true ]; then
    latest=$(ls -t "$LOG_DIR"/iteration-*.log 2>/dev/null | head -1)
    if [ -z "$latest" ]; then
        echo "No logs yet. Start autopilot first, then run: ./autopilot.sh --tail"
        exit 1
    fi
    echo "Tailing: $latest (Ctrl+C to stop)"
    tail -f "$latest"
    exit 0
fi

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
DIM='\033[2m'
NC='\033[0m'

iteration=0
started_at=$(date '+%Y-%m-%d %H:%M:%S')
issues_shipped=0

while true; do
    iteration=$((iteration + 1))
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    log_file="$LOG_DIR/iteration-${iteration}-$(date '+%Y%m%d-%H%M%S').log"

    # Check how many MVP issues remain
    remaining=$(gh issue list -R "$REPO" --milestone "MVP (Weeks 1-4)" --state open --json number -q 'length' 2>/dev/null || echo "?")

    if [ "$remaining" = "0" ]; then
        echo ""
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${GREEN}  MVP COMPLETE — All issues shipped!${NC}"
        echo -e "${GREEN}  Total iterations: ${iteration}${NC}"
        echo -e "${GREEN}  Issues shipped: ${issues_shipped}${NC}"
        echo -e "${GREEN}  Started: ${started_at}${NC}"
        echo -e "${GREEN}  Finished: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        exit 0
    fi

    # Show which issues are still open
    open_issues=$(gh issue list -R "$REPO" --milestone "MVP (Weeks 1-4)" --state open --json number,title -q '.[] | "  #\(.number) \(.title)"' 2>/dev/null || echo "  (could not fetch)")

    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  Iteration #${iteration} — ${timestamp}${NC}"
    echo -e "${BLUE}  Open MVP issues: ${remaining}${NC}"
    echo -e "${DIM}${open_issues}${NC}"
    echo -e "${BLUE}  Log: ${log_file}${NC}"
    if [ "$VERBOSE" = true ]; then
        echo -e "${CYAN}  Mode: VERBOSE (streaming Claude output)${NC}"
    else
        echo -e "${DIM}  Mode: quiet (use --verbose or --tail to see output)${NC}"
    fi
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # Track issues before this iteration
    before_count=$remaining

    # Run Claude with the prompt — fresh process, no session continuity
    prompt=$(cat "$PROMPT_FILE")
    iter_start=$(date +%s)

    if [ "$VERBOSE" = true ]; then
        # Stream JSON output, extract text in realtime, log everything
        claude -p --dangerously-skip-permissions \
            --output-format stream-json \
            "$prompt" \
            2>"$log_file.stderr" | tee "$log_file.raw" | \
            python3 -c "
import sys, json
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        obj = json.loads(line)
        # Tool use events
        if obj.get('type') == 'tool_use':
            name = obj.get('tool', {}).get('name', obj.get('name', ''))
            inp = obj.get('tool', {}).get('input', obj.get('input', ''))
            if name == 'Bash':
                cmd = inp.get('command', '') if isinstance(inp, dict) else ''
                print(f'\033[2m  ⚡ {name}: {cmd[:120]}\033[0m', flush=True)
            elif name in ('Read', 'Write', 'Edit', 'Glob', 'Grep'):
                path = inp.get('file_path', inp.get('pattern', '')) if isinstance(inp, dict) else ''
                print(f'\033[2m  ⚡ {name}: {path[:120]}\033[0m', flush=True)
            else:
                print(f'\033[2m  ⚡ {name}\033[0m', flush=True)
        # Assistant text output
        elif obj.get('type') == 'assistant' and 'message' in obj:
            text = ''
            for block in obj['message'].get('content', []):
                if isinstance(block, dict) and block.get('type') == 'text':
                    text += block.get('text', '')
                elif isinstance(block, str):
                    text += block
            if text.strip():
                print(text.strip(), flush=True)
        # Result message
        elif obj.get('type') == 'result':
            text = obj.get('result', '')
            if text:
                print(text[:500], flush=True)
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
" || true
        # Also save readable log
        python3 -c "
import json, sys
for line in open('$log_file.raw'):
    try:
        obj = json.loads(line.strip())
        if obj.get('type') == 'assistant':
            for b in obj.get('message',{}).get('content',[]):
                if isinstance(b,dict) and b.get('type')=='text': print(b['text'])
        elif obj.get('type') == 'result':
            print(obj.get('result',''))
    except: pass
" > "$log_file" 2>/dev/null || cp "$log_file.raw" "$log_file"
    else
        # Log only, show progress dots
        claude -p --dangerously-skip-permissions "$prompt" \
            > "$log_file" 2>&1 &
        claude_pid=$!

        # Show progress while Claude runs
        while kill -0 $claude_pid 2>/dev/null; do
            printf "."
            sleep 10
        done
        wait $claude_pid 2>/dev/null || true
        echo ""
    fi

    iter_end=$(date +%s)
    duration=$(( iter_end - iter_start ))
    minutes=$(( duration / 60 ))
    seconds=$(( duration % 60 ))

    # Check if an issue was shipped this iteration
    after_count=$(gh issue list -R "$REPO" --milestone "MVP (Weeks 1-4)" --state open --json number -q 'length' 2>/dev/null || echo "?")

    if [ "$after_count" != "?" ] && [ "$before_count" != "?" ] && [ "$after_count" -lt "$before_count" ]; then
        shipped=$(( before_count - after_count ))
        issues_shipped=$(( issues_shipped + shipped ))
        echo -e "${GREEN}  ✓ Shipped ${shipped} issue(s) in ${minutes}m ${seconds}s (${issues_shipped} total)${NC}"
    else
        # Check last few lines of log for what happened
        tail_output=$(tail -5 "$log_file" 2>/dev/null | head -3)
        echo -e "${YELLOW}  ○ No issues shipped this iteration (${minutes}m ${seconds}s)${NC}"
        echo -e "${DIM}  Last output: ${tail_output}${NC}"
    fi

    echo -e "${DIM}  Starting next iteration in 5s...${NC}"
    sleep 5
done
