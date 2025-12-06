from defs import (
  target_spellcard_data_path, target_checkpoint_path, 
  CellStateDict, CellState, Team, Coord, OpType,
  N, max_hp, privileged_spellcard_ids
)
import pandas as pd
import pickle
import os
from typing import Dict, List, Optional

# global state var
## in state_dict
team_cell_state_dict: Dict[Team, CellStateDict] = {}
team_hp_dict: Dict[Team, Dict[Coord, int]] = {}
spellcard_id_map: Dict[Coord, int] = {}

## always read afresh
spellcard_data: pd.DataFrame = pd.DataFrame()

## always calculated
spellcard_score_map: Dict[Coord, int] = {}

## always reset
sys_op: OpType = OpType.TOGGLE_PENDING
sys_team: Team = Team.RED

# checkpoint
max_checkpoint_id = 1000
def try_load_latest_checkpoint():
  print(">> Attempting to load latest checkpoint...")
  for id in range(max_checkpoint_id, 0, -1):
    path = target_checkpoint_path.format(id=id)
    try:
      load_checkpoint(path)
      print("<< Checkpoint loaded from", path)
      return True
    except FileNotFoundError:
      continue
  print("<< No checkpoint found, starting fresh.")
  return False
    
def try_save_latest_checkpoint():
  print(">> Attempting to save latest checkpoint...")
  for id in range(max_checkpoint_id, 0, -1):
    path = target_checkpoint_path.format(id=id - 1)
    if os.path.exists(path) or id == 1:
      path = target_checkpoint_path.format(id=id)
      save_checkpoint(path)
      print("<< Checkpoint saved to", path)
      return
  print("<< Warning: No valid checkpoint slot found.")

def save_checkpoint(path):
    
  state_dict = {
    "team_cell_state_dict": team_cell_state_dict,
    "team_hp_dict": team_hp_dict,
    "spellcard_id_map": spellcard_id_map
  }
  pickle.dump(state_dict, open(path, "wb"))

def load_checkpoint(path):
  global team_cell_state_dict, team_cell_state_dict, team_hp_dict, spellcard_id_map
  data = pickle.load(open(path, "rb"))
  try:
    team_cell_state_dict = data.get("team_cell_state_dict")
    team_hp_dict = data.get("team_hp_dict")
    spellcard_id_map = data.get("spellcard_id_map")
  except KeyError as e:
    print(f"Corrupted checkpoint {path}: {e}")

# Initialization
def init_state(reset: bool = False):
  print(">> init state")
  try:
    load_spellcard_data()
  except Exception as e:
    print(f"Error loading spellcard data\n what: \n{e}")
    raise e
  
  if not reset and try_load_latest_checkpoint():
    pass
  else:
    init_team_cell_state_dict()
    init_team_hp_dict()
    # if len(spellcard_id_map) == 0:
    #   sample_spellcard() # init_spellcard_id_map
    
    # always resample spellcards on reset
    sample_spellcard() # init_spellcard_id_map
    
  init_spellcard_score_map()
    
  # print spellcard_id_map
  print("Spellcard sample results:")
  for i in range(N):
    print(" | ", end="")
    for j in range(N):
      print(f"{spellcard_id_map[(i,j)]:3d} ", end="")
    print("|")
  print("<< init state")
  
  


def load_spellcard_data():
  df = pd.read_csv(target_spellcard_data_path)
  
  # drop Placeholder 1~6 columns
  for i in range(1, 7):
    placeholder_col = f"Placeholder{i}"
    if placeholder_col in df.columns:
      df = df.drop(columns=[placeholder_col])
      
  # drop where score is NaN, and warn if any
  df['Score'] = pd.to_numeric(df['Score'], errors='coerce')
  if df['Score'].isnull().any():
    invalid_rows = df[df['Score'].isnull()]
    print("================================================================")
    print(f"Warning: The following {len(invalid_rows)} rows have NaN Score and will be dropped:")
    print(invalid_rows[['SeriesID', 'LocalID', 'SpellcardName']].head(10))
    print("......")
    print("================================================================")
    df = df.dropna(subset=['Score'])
    
  # fill comment nan to ''
  df['Comment'] = df['Comment'].fillna('')
  
  # if LocalID is NaN, replace to 0
  df['LocalID'] = df['LocalID'].fillna(0)

  # Cast IDs to int
  # for col in ['LocalID', 'GlobalID']:
  for col in ['GlobalID']:
    df[col] = pd.to_numeric(df[col], errors='coerce')

  # format 'CanonicalID' to "{SeriesID}-{LocalID}"
  # if LocalID is 0, format it to "{SeriesID}-NonSpell" or "{SeriesID}-NS"
  # Note: some LocalID is now 6A/6B, indicating the stage, so use str instead. NS is deprecated.
  df['CanonicalID'] = df.apply(
    lambda row: f"{row['SeriesID']}-{row['LocalID']}" 
                if row['LocalID'] != 0 else 
                f"{row['SeriesID']}-ns",
    axis=1
  )
  
  global spellcard_data
  spellcard_data = df

def init_team_cell_state_dict():
  global team_cell_state_dict
  for team in [Team.RED, Team.BLUE]:
    team_cell_state_dict[team] = {
      (i, j): CellState.UNCHECKED for i in range(N) for j in range(N)
    }
    
def init_team_hp_dict():
  global team_hp_dict
  for team in [Team.RED, Team.BLUE]:
    team_hp_dict[team] = {
      (i, j): max_hp for i in range(N) for j in range(N)
    }

def sample_spellcard():
  global spellcard_id_map
  # sample NxN unique int from len(spellcard_data)
  total_spellcards = len(spellcard_data)
  import random
  sampled_indices = random.sample(range(total_spellcards), N * N)
  sampled_indices = inject_privileged_spellcard(
    sampled_indices,
    privileged_spellcard_ids
  )
  spellcard_id_map = {
    (i, j): sampled_indices[i * N + j] for i in range(N) for j in range(N)
  }
  
def inject_privileged_spellcard(sampled_indices: List[int], privileged_spellcard_ids: List[int]):  
  import random
  positions = random.sample(range(N * N), len(privileged_spellcard_ids))
  to_evict = [sampled_indices[pos] for pos in positions]
  
  for pos, sc_global_id in zip(positions, privileged_spellcard_ids):
    # seek by GlobalID in spellcard_data
    sc_ids = spellcard_data.index[spellcard_data['GlobalID'] == sc_global_id].tolist()
    if len(sc_ids) != 1:
      raise RuntimeError(f"privileged spellcard with global id {sc_global_id} not found or not unique. len={len(sc_ids)}")
    
    sc_id = sc_ids[0]
    if sc_id not in sampled_indices or \
       sc_id in to_evict:
      sampled_indices[pos] = sc_id
  return sampled_indices


def init_spellcard_score_map():
  global spellcard_score_map
  spellcard_score_map = {
    xy: spellcard_data.iloc[sc_id]['Score']
    for xy, sc_id in spellcard_id_map.items()
  }
  
  
# Access Interface
def get_spellcard(xy: Coord):
  sc_id = spellcard_id_map.get(xy)
  sc_data = spellcard_data[sc_id]
  
  return {
    "name": sc_data['SpellcardName'],
    "score": sc_data['Score'],
    "index": sc_data['CanonicalID'],
    "comment": sc_data['Comment']
  }
  
def get_cell_state(team: Team, xy: Coord) -> CellState:
  return team_cell_state_dict[team][xy]

def set_cell_state(team: Team, xy: Coord, state: CellState):
  team_cell_state_dict[team][xy] = state

def get_cell_hp(team: Team, xy: Coord) -> int:
  return team_hp_dict[team][xy]

def inc_cell_hp(team: Team, xy: Coord, delta: int):
  team_hp_dict[team][xy] += delta
  if team_hp_dict[team][xy] > max_hp:
    team_hp_dict[team][xy] = max_hp
  if team_hp_dict[team][xy] < 0:
    team_hp_dict[team][xy] = 0

def get_pending_coord(team: Team) -> Optional[Coord]:
  for xy, state in team_cell_state_dict[team].items():
    if state == CellState.PENDING:
      return xy
  return None

def get_hp(team: Team) -> int:
  xy = get_pending_coord(team)
  if xy is None:
    return max_hp
  return get_cell_hp(team, xy)

def inc_hp(team: Team, delta: int):
  xy = get_pending_coord(team)
  if xy is None:
    return
  inc_cell_hp(team, xy, delta)

if __name__ == "__main__":
  init_state()
  try_save_latest_checkpoint()