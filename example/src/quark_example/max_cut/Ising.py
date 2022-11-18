import networkx as nx

from typing import TypedDict

from applications.Mapping import *
from solvers.Solver import Solver

from qat.opt import MaxCut

class Ising(Mapping):
    """
    Ising formulation for MaxCut.
    """

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
        maxcut = MaxCut(graph)
        return {"ising":maxcut, "graph":graph}, round(time() * 1000 - start, 3)
        
    def reverse_map(self, result) -> (any, float):
        energy = result[0]
        return (None if energy is None else -energy, result[1]), 0
        
    def get_solver(self, solver_option: str) -> Solver:
        raise NotImplementedError(f"Solver Option {solver_option} not implemented")
    