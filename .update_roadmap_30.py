import subprocess

result = subprocess.run(
    ["gh", "issue", "view", "44", "-R", "robert197/baky", "--json", "body", "-q", ".body"],
    capture_output=True,
    text=True,
)
body = result.stdout

body = body.replace("- [ ] #8 ", "- [x] #8 ", 1)
body = body.replace("- [ ] #30 ", "- [x] #30 ", 1)

subprocess.run(["gh", "issue", "edit", "44", "-R", "robert197/baky", "--body", body])
print("Roadmap updated")
