import os
import sys

try:
    ROOT = __file__
except NameError:
    ROOT = None

CG_PATH = "/kaggle_simulations/agent"
for path in ([os.path.dirname(os.path.abspath(ROOT))] if ROOT else []) + [CG_PATH]:
    if path and os.path.isdir(path) and path not in sys.path:
        sys.path.insert(0, path)

from cg.api import to_observation_class


def read_deck():
    with open("deck.csv", encoding="utf-8") as handle:
        return [int(line.strip()) for line in handle if line.strip()]


def agent(obs):
    obs = to_observation_class(obs)
    if obs.select is None:
        return read_deck()
    min_count = obs.select.minCount
    option_count = len(obs.select.option)
    return list(range(min_count if min_count <= option_count else option_count))
