#!/usr/bin/env python3
"""Update roadmap issue #44 to check off issue #10."""
import subprocess

result = subprocess.run(
    ["gh", "api", "repos/robert197/baky/issues/44", "--jq", ".body"],
    capture_output=True,
    text=True,
)
body = result.stdout

updated = body.replace("- [ ] #10 ", "- [x] #10 ")

if updated == body:
    print("No changes needed - item may already be checked")
else:
    result = subprocess.run(
        ["gh", "api", "repos/robert197/baky/issues/44", "--method", "PATCH", "--field", "body=" + updated],
        capture_output=True,
        text=True,
    )
    print("returncode:", result.returncode)
    if result.returncode == 0:
        print("Roadmap updated: #10 checked off")
    else:
        print("Error:", result.stderr[:500])
