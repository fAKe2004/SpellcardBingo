"""Flask server for Spellcard Bingo (two-team, server-managed state).

Endpoints:
- GET  /state     -> returns current board, cell states per team, sys op/team, colors, and scores
- POST /switch    -> accepts { team?: 'red'|'blue', op?: 'toggle_check'|'toggle_pending' } and updates sys selection
- POST /click     -> accepts { r: int, c: int } and applies current op for current team

All game state and scoring are managed in Python (state.py, calc_score.py).
"""

from flask import Flask, jsonify, request, send_from_directory
from typing import Dict, List, Tuple
import os

from defs import N, Team, CellState, OpType, color_mapping, max_hp
import state as S
import calc_score as CS

app = Flask(__name__, static_folder="static", static_url_path="")



def _enum_from_str_team(team_str: str) -> Team:
    s = (team_str or "").lower()
    if s == Team.RED.value:
        return Team.RED
    if s == Team.BLUE.value:
        return Team.BLUE
    raise ValueError(f"Invalid team: {team_str}")


def _enum_from_str_op(op_str: str) -> OpType:
    s = (op_str or "").lower()
    if s == OpType.TOGGLE_CHECK.value:
        return OpType.TOGGLE_CHECK
    if s == OpType.TOGGLE_PENDING.value:
        return OpType.TOGGLE_PENDING
    raise ValueError(f"Invalid op: {op_str}")


def _card_payload() -> List[List[Dict]]:
    """Builds NxN card view from state's sampled spellcards.

    Note: We intentionally avoid S.get_spellcard() because it indexes DataFrame by label;
    we'll read S.spellcard_data using iloc with S.spellcard_id_map directly.
    """
    grid: List[List[Dict]] = []
    for r in range(N):
        row: List[Dict] = []
        for c in range(N):
            sc_id = S.spellcard_id_map.get((r, c))
            rec = S.spellcard_data.iloc[int(sc_id)] if sc_id is not None else None
            row.append({
                "name": None if rec is None else str(rec.get('SpellcardName', '')),
                "score": 0 if rec is None else int(rec.get('Score', 0)),
                "index": None if rec is None else str(rec.get('CanonicalID', '')),
                "comment": None if rec is None else str(rec.get('Comment', '')),
            })
        grid.append(row)
    return grid


def _cells_payload() -> Dict[str, List[List[str]]]:
    def team_grid(team: Team) -> List[List[str]]:
        g: List[List[str]] = []
        d = S.team_cell_state_dict[team]
        for r in range(N):
            row: List[str] = []
            for c in range(N):
                row.append(d[(r, c)].value)
            g.append(row)
        return g

    return {
        Team.RED.value: team_grid(Team.RED),
        Team.BLUE.value: team_grid(Team.BLUE),
    }


def _scores_payload() -> Dict[str, int]:
    return {
        Team.RED.value: int(CS.calc_total_score(Team.RED)),
        Team.BLUE.value: int(CS.calc_total_score(Team.BLUE)),
    }


def _sys_payload() -> Dict[str, str]:
    return {"team": S.sys_team.value, "op": S.sys_op.value}

def _pending_payload() -> Dict:
    red_xy = S.get_pending_coord(Team.RED)
    blue_xy = S.get_pending_coord(Team.BLUE)
    def pack(team: Team, xy):
        if xy is None:
            return {"xy": None, "hp": None}
        hp_val = S.get_hp(team)
        return {"xy": [xy[0], xy[1]], "hp": (None if hp_val is None else int(hp_val))}
    return {
        "red": pack(Team.RED, red_xy),
        "blue": pack(Team.BLUE, blue_xy),
        "max_hp": int(max_hp),
    }


def _state_payload() -> Dict:
    return {
        "N": N,
        "card": _card_payload(),
        "cells": _cells_payload(),
        "sys": _sys_payload(),
        "colors": {"red": color_mapping[Team.RED], "blue": color_mapping[Team.BLUE], "both": color_mapping["both"]},
        "scores": _scores_payload(),
        "pending": _pending_payload(),
    }


def _clear_pending_for_team(team: Team) -> None:
    d = S.team_cell_state_dict[team]
    for k, v in list(d.items()):
        if v == CellState.PENDING:
            S.set_cell_state(team, k, CellState.UNCHECKED)


def _apply_click(r: int, c: int) -> None:
    team = S.sys_team
    xy: Tuple[int, int] = (r, c)
    cur = S.get_cell_state(team, xy)
    # New click semantics (bypass sys_op for processing):
    # - Clicking a PENDING cell -> CHECK it
    # - Clicking a CHECKED cell -> UNCHECK it
    # - Clicking an UNCHECKED cell -> set PENDING (only one pending per team)
    if cur == CellState.PENDING:
        S.set_cell_state(team, xy, CellState.CHECKED)
        _clear_pending_for_team(team)  # ensure no lingering pending
    elif cur == CellState.CHECKED:
        S.set_cell_state(team, xy, CellState.UNCHECKED)
        # don't touch pending elsewhere when unchecking
    else:  # UNCHECKED
        _clear_pending_for_team(team)
        S.set_cell_state(team, xy, CellState.PENDING)


@app.route("/state")
def api_state():
    return jsonify(_state_payload())


@app.route("/switch", methods=["POST"])
def api_switch():
    data = request.get_json(force=True) or {}
    team_str = data.get("team")
    op_str = data.get("op")
    # Debug print
    payload = {}
    if team_str is not None:
        payload["team"] = team_str
    if op_str is not None:
        payload["op"] = op_str
    print(f"-- switch {payload}")
    try:
        if team_str is not None:
            S.sys_team = _enum_from_str_team(team_str)
        if op_str is not None:
            S.sys_op = _enum_from_str_op(op_str)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_state_payload())


@app.route("/click", methods=["POST"])
def api_click():
    data = request.get_json(force=True) or {}
    r_raw = data.get("r")
    c_raw = data.get("c")
    if r_raw is None or c_raw is None:
        return jsonify({"error": "Missing r/c"}), 400
    try:
        r = int(r_raw)
        c = int(c_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid r/c"}), 400
    if not (0 <= r < N and 0 <= c < N):
        return jsonify({"error": "Out of range"}), 400
    # Debug print
    print(f"-- click {{'r': {r}, 'c': {c}}}")
    _apply_click(r, c)
    return jsonify(_state_payload())


@app.route("/hp", methods=["POST"])
def api_hp():
    data = request.get_json(force=True) or {}
    team_str = data.get("team")
    delta = data.get("delta", 0)
    try:
        if not isinstance(team_str, str):
            raise ValueError("missing team")
        team = _enum_from_str_team(team_str)
        delta = int(delta)
    except Exception:
        return jsonify({"error": "Invalid team/delta"}), 400

    xy = S.get_pending_coord(team)
    if xy is None:
        print(f"-- hp {{'team': '{team.value}', 'delta': {delta}}} -> no-pending")
        return jsonify({"error": "No pending cell for team"}), 400

    # Debug print
    print(f"-- hp {{'team': '{team.value}', 'delta': {delta}}}")
    # inc_hp should handle positive or negative delta and clamp internally
    S.inc_hp(team, delta)

    return jsonify(_state_payload())


@app.route("/reset", methods=["POST"])
def api_reset():
    """Re-initialize game state (data reload, new board, reset states)."""
    print("-- reset {}")
    try:
        S.init_state(reset=True)
        return jsonify(_state_payload())
    except Exception as e:
        return jsonify({"error": f"reset failed: {e}"}), 500


@app.route("/")
def index():
    static_dir = app.static_folder or os.path.join(os.path.dirname(__file__), "static")
    return send_from_directory(static_dir, "index.html")

def is_serving_process(app) -> bool:
    """Determines if the current process is the one serving requests.

    In Flask debug mode, the reloader spawns a child process to serve requests
    (WERKZEUG_RUN_MAIN == 'true'). In non-debug mode, this process serves.
    """
    return (os.environ.get("WERKZEUG_RUN_MAIN") == "true") or (not app.debug)
    

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()  # to avoid Flask's arg parsing issues
    parser.add_argument("--resume", action="store_true")
    reset = not parser.parse_args().resume

    S.init_state(reset=reset)
    # Initialize state on server start
    try:
        # Start Flask server
        app.run(debug=True, host="0.0.0.0")

    except Exception as e:
        print(f"Failed to start server: {e}")
    finally:
        if is_serving_process(app):
            S.try_save_latest_checkpoint()
