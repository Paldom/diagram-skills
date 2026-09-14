# Demo: the routing step, headless, in a throwaway directory.
# Render: vhs assets/demo.tape   Validate first: vhs validate assets/demo.tape
# The run is real: `claude -p` drives the diagram-brief skill in a scratch
# install. The waiting is hidden; the typed ask and the brief it wrote are not.
# Override the install source for a local render:
#   DIAGRAM_SKILLS_SRC=/path/to/checkout vhs assets/demo.tape
Output assets/demo.gif

Require claude
Require npx

Set Shell "bash"
Set FontSize 16
Set Width 1200
Set Height 640
Set Padding 20
Set Theme "GitHub Dark"
Set TypingSpeed 40ms
Set Framerate 12
Set WaitTimeout 8m

# --- hidden setup: throwaway dir, install the skills, clear ---
Hide
Type "rm -rf /tmp/diagram-skills-demo && mkdir -p /tmp/diagram-skills-demo && cd /tmp/diagram-skills-demo && git init -q . && npx -y skills@1.5.19 add ${DIAGRAM_SKILLS_SRC:-Paldom/diagram-skills} -a claude-code -y --copy >/dev/null 2>&1; clear"
Enter
Sleep 3s
Show

Type "claude -p --permission-mode acceptEdits '/diagram-brief LinkedIn post: Stop putting business logic in your API gateway. My take: a gateway should only do auth, rate limiting and routing.'; echo BRIE''F_EXIT=$?"
Sleep 800ms
Enter

# --- the session takes about a minute; skip the waiting, keep the answer ---
Hide
Wait+Screen /BRIEF_EXIT=/
Show
Sleep 7s

Type "clear; sed -n '1,26p' diagram-design/*/brief.md"
Sleep 500ms
Enter
Sleep 8s
