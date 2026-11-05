Run my Content Studio daily routine. STUDIO = {{STUDIO_PATH}}

STEP 0, TIMING CHECK (scheduled runs only, do this first):
- Run `date "+%Y-%m-%d %H:%M"` for the local date and time.
- Run `cd "{{STUDIO_PATH}}" && python3 -I studio_cli.py get briefs <today>`.
- SKIP the whole run if the local time is after {{SKIP_AFTER}} or a brief for today already exists. Skipping means no scan, no writes, no messages. Reply with one line: "Skipped: the computer was not on at {{RUN_TIME}}. Next run tomorrow." Missed mornings are never caught up.

Then read "{{STUDIO_PATH}}/routine-prompt.md" and follow it exactly, starting with its Step 0 (the Taplio LinkedIn MCP check). If the Taplio LinkedIn MCP is not connected, stop and show the connection links from that file.

Never post, comment, draft, schedule or email. Never change my own choices, notes, idea links or manual ideas, and never delete saved items.
