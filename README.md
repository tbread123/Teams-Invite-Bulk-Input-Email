# Teams Invite Typer

Types emails into the Microsoft Teams invite box one at a time.

## File locations


| File | What it is |
| --- | --- |
| `emails.txt` | Email list (edit this) |
| `teams_invite.py` | The typer script |
| `Start Teams Invite.command` | Double-click to run |

## How to use

1. Open the Teams invite box and click the email field.
2. Click **Start** on the panel, or press **F6**.
3. Keep the Teams field focused during the 5-second countdown.
4. The script types each email, waits 3 seconds, then presses Enter.

**Stop:** move the mouse to the **top-left** corner of the screen, or click **Stop**.

## How to change the email list

Edit **only** `/Users/huangzetao/game/emails.txt`.

- One email per line
- Blank lines and lines starting with `#` are ignored
- Click **Start** after saving — the script reloads the file automatically

You do not need to edit `teams_invite.py`.
