from time import time

from applications import Mapping
from applications.Application import *

from tqpm.max_cut.MaxCut import MaxCut

import networkx as nx

class GraphCreationTest(Application2):
    def __init__(self):
        """
        Constructor method
        """
        super().__init__("Test")
        self.maxcut = MaxCut()

    def get_solution_quality_unit(self) -> str:
        return "Normalized Link Count"

    def get_mapping(self, mapping_option: str) -> Mapping:
        raise NotImplementedError(f"Mapping Option {mapping_option} not implemented")
        
    def get_parameter_options(self) -> dict:
        param_opts = self.maxcut.get_parameter_options()
        param_opts["graph_type"]["values"] = ["erdos-renyi"]
        return param_opts

    def regenerate_on_iteration(self, config) -> bool:
        return self.maxcut.regenerate_on_iteration(config)
 
    def generate_problem(self, config: MaxCut.Config, rep_count: int) -> nx.Graph:
        return self.maxcut.generate_problem(config, rep_count)

    def validate(self, solution: list) -> (bool, float):
        #no constraints -> no invalid solutions
        return not solution is None, 0.0
        
    def evaluate(self, solution: (int)) -> (float, float):
        start = time() * 1000
        n = len(self.problem)
        nl_exp = n*(n-1)/4.0
        print("evaluate", solution, nl_exp)
        return  solution/nl_exp, round(time() * 1000 - start, 3)
    
    def save(self, path: str, rep_count: int) -> None:
        self.maxcut.save(path, rep_count)
