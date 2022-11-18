from typing import TypedDict

from solvers.Solver import *
from devices.Device import Device

from quark_example.max_cut.max_cut_utils import number_of_cuts 
from devices.Local import Local

class BruteForce(Solver):
    def __init__(self):
        """
        Constructor method
        """
        super().__init__()
        self.device_options = ["Local"]
        
    class Config(TypedDict):
        pass
    
    def get_device(self, device_option: str) -> Device:
        return Local()

    def get_parameter_options(self) -> dict:
        return {}

    def run(self, mapped_problem: dict, device_wrapper: any, config: Config, **kwargs: dict) -> (any, float):
        start = time() * 1000

        graph = mapped_problem["graph"]
        n = len(graph)
        nbcuts_max = None
        solution = None
        for i in range(2**n):
            bitstr = "{0:b}".format(i).zfill(n)
            sol = [int(s)*2 -1 for s in bitstr ]
            nbcuts = number_of_cuts(graph, sol)
            if nbcuts_max is None or nbcuts > nbcuts_max:
                nbcuts_max = nbcuts
                solution = sol
        return (nbcuts_max, solution), round(time() * 1000 - start, 3), ""    

class LinkCount(Solver):
    def __init__(self):
        """
        Constructor method
        """
        super().__init__()
        self.device_options = ["Local"]

    class Config(TypedDict):
        pass

    def get_device(self, device_option: str) -> Device:
        return Local()

    def get_parameter_options(self) -> dict:
        return {}

    def run(self, mapped_problem: dict, device_wrapper: any, config: Config, **kwargs: dict) -> (any, float):
        start = time() * 1000

        graph = mapped_problem["graph"]
        n = len(graph.edges)
        return n, round(time() * 1000 - start, 3), ""

        

