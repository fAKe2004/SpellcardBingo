# Spellcard Bingo!

This is the UI of `Spellcard Bingo` game for SJTU Touhou Festival 2025.

The game is inspired by [th-bingo](https://github.com/CuteReimu/th-bingo).

---

## Manual

### Quick start

Requirements:
- Python 3.10+
- Install dependencies: `pip install -r requirements.txt`
- Data file: `data/SpellcardData.csv`

Run the server:

```bash
python app.py           # start fresh (new random board)
python app.py --resume  # resume from the latest checkpoint if available
```

Open http://localhost:5000 in a browser. The page is optimized for on-stage display.

### Top HUD UI

- Left and right: team titles “RED” and “BLUE”.
- Center row labels: “score” and “hp”.
- Under each team title you’ll see the team’s total score and its HP controls.

### Selecting a team

Use the “select” button below a team label to make that team active. The active team’s button shows “selected”. All clicks on the grid affect the currently selected team only.

### Clicking cells (core logic)

For the currently selected team, cell clicks cycle through these states:

1. Unchecked → Pending
2. Pending → Checked
3. Checked → Unchecked

- A team can have at most one Pending cell at a time. Clicking an Unchecked cell when the team already has a Pending cell will move the Pending marker to the new cell.

### Adjusting HP

- Each team has per-cell HP controls “- hp +” under the HUD.
- HP is tied to that team’s current Pending cell:
	- When a team has a Pending cell, its HP value appears and the “-”/“+” buttons are enabled.
	- If the team has no Pending cell, HP shows “--” and the buttons are disabled.

### Resetting the game

Click “Reset” to reinitialize everything

### Scoring

- Per‑cell scores come from the data file and are shown in the bottom‑right of each cell.
- Team totals are calculated on the server (see `calc_score.py`) from sum of checked cells and bingo bouns.

### Persistence and resume

- On startup, the server will start fresh by default. Use `--resume` to restore from the latest available checkpoint.
- On shutdown, the server saves a checkpoint containing board layout, per‑team cell states, and HP.
- Checkpoints are written as pickle files to `data/checkpoint-{id}.pickle` and the latest is loaded when resuming.