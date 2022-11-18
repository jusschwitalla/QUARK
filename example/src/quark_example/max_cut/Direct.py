from typing import TypedDict

import networkx as nx

from applications.Mapping import *
from solvers.Solver import Solver

class Direct(Mapping):
    def __init__(self):
        """
        Constructor method
        """
        super().__init__()

    def get_parameter_options(self) -> dict:
        return {}
        
    class Config(TypedDict):
        pass
    
    def map(self, graph: nx.Graph, config: Config) -> (dict, float):
        start = time() * 1000
        return {"graph":graph}, round(time() * 1000 - start, 3)
        
    def get_solver(self, solver_option: str) -> Solver:
        raise NotImplementedError(f"Solver Option {solver_option} not implemented")
