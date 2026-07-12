import random
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

def generate_scenario():

    nodes = random.randint(5,50)
    traffic = random.choice(["low","medium","high"])

    scenario = {
        "nodes": nodes,
        "traffic": traffic
    }

    return scenario

scenario = generate_scenario()

print("Generated scenario:",scenario)

with open(DATA_DIR/"scenario.json","w") as f:
    json.dump(scenario,f,indent=2)