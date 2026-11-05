# Content Studio setup (instructions for the AI assistant)

You are setting up Content Studio for the user. Do the steps in order. Keep your messages to the user short and friendly; they may not be technical. Ask only the questions listed in Step 3.

## Requirements
- **Claude Code** (the Claude desktop app's Code tab, or the `claude` CLI). A plain chat in claude.ai can't run the local board; if that's where you are, tell the user to open this repo in Claude Code instead.
- Python 3.9 or newer (`python3 --version`). macOS and Linux work as is; on Windows use WSL.
- The **Taplio LinkedIn MCP** (Step 1). It is mandatory.

## Step 1: Taplio LinkedIn MCP (mandatory, do not skip)
Run the check in [CLAUDE.md](CLAUDE.md), Rule 1: find the Taplio LinkedIn MCP tools and call `get_me`.
- Not connected: send the exact message from CLAUDE.md with the setup video (https://www.youtube.com/watch?v=afjA8ifgo6A) and the Taplio LinkedIn MCP page (https://taplio.com/taplio-linkedin-mcp). Stop and wait. When they say it's connected, check again. In the terminal CLI, a newly added MCP only appears after Claude Code restarts.
- Connected: note the tool prefix (for example `mcp__taplio__`), and keep the `get_me` result. It holds their profile and LinkedIn preferences, which you'll use to pre-fill Step 3.

## Step 2: Put the folder in the right place
If this repo isn't on their computer yet, clone it: `git clone https://github.com/annix-1/linkedin-content-studio.git ~/ContentStudio`.
On macOS, recommend `~/ContentStudio`, not Desktop, Documents or Downloads: macOS blocks background services from reading those folders, which breaks auto-start (Step 8). If they already cloned it somewhere else, offer to move it there.
From here on, STUDIO = the folder's full path.

## Step 3: Short interview (pre-fill from `get_me`)
Suggest answers from their Taplio profile and ask them to confirm or edit, in one message:
1. First name.
2. Niche: who they are and what they post about (one sentence).
3. Audience: who reads them (one sentence).
4. 3 or 4 content pillars.
5. 2 to 5 LinkedIn creators whose style they like.
6. Anything they never want to see (e.g. "comment X for the doc" posts).
7. What time they want the brief on weekdays (default 08:00), and the language of the brief.
8. Optional: do they want the brief sent to their own Slack DM? Only if a Slack connector is available. If yes, get their Slack member ID (their profile, ⋯ menu, "Copy member ID").

## Step 4: Write config.json
Copy `config.example.json` to `config.json` and fill it from Step 3. Build `searchKeywords` from the defaults plus 3 to 5 niche terms. Set:
- `run.time` and `run.skipIfStartedAfter` (30 minutes after `run.time`).
- `taplioLinkedInMcp.verifiedAt` = the current ISO timestamp and `taplioLinkedInMcp.serverName` = the prefix from Step 1. Only write these after a successful `get_me`. The server will not start without them.
`config.json` stays on their computer (it's in .gitignore).

## Step 5: Permissions, so the morning run never stops to ask
`.claude/settings.json` already allows the project's own scripts. Add the three read-only Taplio LinkedIn MCP tools with their real prefix to `STUDIO/.claude/settings.local.json` (create it if needed), for example:
```json
{ "permissions": { "allow": [
  "mcp__taplio__get_me", "mcp__taplio__search_inspiration", "mcp__taplio__find_comments_to_reply"
] } }
```
If they turned on Slack, add only the Slack send-message tool. Never allow Taplio tools that publish, schedule, comment or like.

## Step 6: Start the board
Run `cd "STUDIO" && python3 -I server.py` in the background and open http://localhost:8020 (or their port). If it prints the Taplio LinkedIn MCP message, go back to Step 1.

## Step 7: First run, right now
Follow [routine-prompt.md](routine-prompt.md) once, now, without the timing check, so the board fills with today's cards, trends and ideas. Tell them how to use it: ✓ save or follow, ✕ pass, link saved pieces to an idea, add their own ideas. The routine learns from every choice.

## Step 8: Run it every weekday morning
- **Claude desktop app (recommended):** create a local scheduled task named "Content Studio" for weekdays at `run.time` (cron `0 8 * * 1-5` for 08:00), with working folder STUDIO, and use [scheduled-task-prompt.md](scheduled-task-prompt.md) as the prompt with `{{STUDIO_PATH}}`, `{{RUN_TIME}}` and `{{SKIP_AFTER}}` filled in. If you have a tool to create scheduled tasks, use it; otherwise walk them through creating it in the app. Scheduled tasks run while the app is open and the computer is awake. A missed morning is skipped, not caught up.
- **Terminal only:** they open Claude Code in STUDIO and type "run my Content Studio routine".

Optional on macOS: so the board is always up when they log in, run `bash scripts/install-autostart-mac.sh "STUDIO"`.

## Step 9: Wrap up
Tell them, in four lines: the board link, when the brief runs, that everything stays on their computer, and that the Taplio LinkedIn MCP is what powers it (if it's ever disconnected, the routine will stop and send the reconnect links).
