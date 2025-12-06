from enum import Enum
from typing import Dict, Tuple, Union

N = 6

class Team(Enum):
  RED = "red"
  BLUE = "blue"
  
color_mapping: Dict[Union[Team, str], str] = {
  Team.RED: "#EE5755",
  Team.BLUE: "#5557EE",
  "both": "#E000E0",
}

class CellState(Enum):
  CHECKED = "checked"
  UNCHECKED = "unchecked"
  PENDING = "pending"

class LineType(Enum):
  ROW = "row"
  COLUMN = "column"
  DIAGONAL = "diagonal"
  
class OpType(Enum):
  TOGGLE_CHECK = "toggle_check"
  TOGGLE_PENDING = "toggle_pending"

Coord = Tuple[int, int]  # (row, col)
CellStateDict = Dict[Coord, CellState]  # Mapping from (row, col) to CellState

# Global Constant
max_hp = 5 # initial challenge times for each spell card

# Always-Sampled Spellcards
privileged_spellcard_ids = [
  364 # 弑神炮麻将山
] # global ids

# Bingo Scoring Rules
bingo_bonus = 10

# File Path
target_spellcard_data_path = "data/SpellcardData.csv"
target_checkpoint_path = "data/checkpoint-{id}.pickle"

# Show Reset Button
show_reset_button = False