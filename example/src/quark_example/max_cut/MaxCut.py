from time import time
import logging

import networkx as nx
import numpy as np

from typing import TypedDict

from applications import Mapping
from applications.Application import Application2
from quark_example.max_cut.max_cut_utils import number_of_cuts

class MaxCut(Application2):

    def __init__(self):
        """
        Constructor method
        """
        super().__init__("MaxCut")
        
    def get_solution_quality_unit(self) -> str:
        return "Normalized Cut Count"

    def get_mapping(self, mapping_option: str) -> Mapping:
        raise NotImplementedError(f"Mapping Option {mapping_option} not implemented.")
        
    def get_parameter_options(self) -> dict:
        """
        Returns the configurable settings for this application

        :return:
                 .. code-block:: python

                      return {
                                "nodes": {
                                    "values": list([3, 4, 6, 8, 10, 14, 16]),
                                    "description": "How many nodes does you graph need?"
                                },
                                "graph_type": {
                                    "values": ["circular", "erdos-renyi"],
                                    "description": "What type of graph do you want?"
                                },
                                "seed": {
                                    "values": list(["random", 79117]),
                                    "description": "The seed used for the graph creation. 'random' implies a randomly chosen seed.",
                                    "exclusive": True
                                }
                            }

        """
        return {
            "graph_type": {
                "values": ["circular", "erdos-renyi"],
                "description": "What type of graph do you want?",
                "exclusive": True
            },
            "seed": {
                "if": {"key":"graph_type", "in" : ["erdos-renyi"]},
                "values": list([79117, "random", None]),
                "description": "The seed used for the graph creation. 'random' implies a randomly chosen seed.",
                "exclusive": True,
                "postproc": lambda s: np.random.randint(100000) if s == "random" else s
            },
            "nodes": {
                "values": list([3, 4, 6, 8, 10, 14, 16]),
                "description": "How many nodes does you graph need?"
            }
        }

    class Config(TypedDict):
        """
        Attributes of a valid config

        .. code-block:: python

             nodes: int

        """
        nodes: int
        graph_type: str
        seed: int


    def regenerate_on_iteration(self, config) -> bool:
        return config['graph_type'] == "erdos-renyi"
    
    def generate_problem(self, config: Config, rep_count: int) -> nx.Graph:
        """
        :return: a graph specifying the concrete max cut problem.
        :rtype: nx.Graph
        """
            
        n = config['nodes']
        self.config = config
        
        G = None
        self.cut_count_max = None
        if config['graph_type'] == "circular":
            #generate circular graph with n nodes
            G = nx.Graph()
            for i in range(n):
                G.add_edge(i, (i+1)%n)
        elif config['graph_type'] == "erdos-renyi":
            #if config["seed"] != None construct the seed the same way as it is done in qscore
            #Note that the seed does only depend on rep_count and not on the configuration.
            seed0 = config["seed"]
            seed = None if seed0 is None else seed0 + rep_count
            logging.info(f"seed for graph creation of size {n} and repetion {rep_count}: {seed}")
            G = nx.erdos_renyi_graph(n, p=0.5, seed=seed)       
        return G
        
    def validate(self, solution: list) -> (bool, float):
        """
        The solution is expected to be of the form [number_of_cuts, partition]
        where number_of_cuts may be an expectation value        
        and partition is either None or a list with elements 1 or -1.
        None is allowed because when using a QAOA solver the quality may be determined from the
        energy expectation value alone without computing the partition.
        """
        #print("validate", solution)
        #check for expected format
        assert len(solution) == 2, "solution should be a of the form [ cut_count, [1,1,-1,...]]"
        if not solution[0] is None:
            assert type(solution[0]) in (int, float, np.float64), f"The expected type of the number of cuts is int or numpy.float64 (if it is an expectation value)but found to be {type(solution[0])}."
        
        partition = solution[1]
        if not partition is None:
            assert type(partition) in (list, np.ndarray), f"The partion should be a list or numpy.ndarray but has type {type(partition)}."
            assert len(partition) == len(self.problem), f"The partition should have length {len(self.problem)} but found to be {len(partition)}"
        
        #no constraints -> no invalid solutions
        return True, 0.0
        
    def _quality(self, cut_count):
        n = len(self.problem)
        if self.config['graph_type'] == "circular":
            #the exact solution:
            cut_count_max = n if n%2 == 0 else (n-1)
            quality_val = cut_count/cut_count_max
        elif self.config['graph_type'] == "erdos-renyi": 
            # See "Benchmarking quantum co-processors in an application-centric, hardware-agnostic and scalable way" 
            # by Simon Martiel, Thomas Ayral, Cyril Allouche
            # eq 3 of this paper reads quality_val = (cut_count - n**2/8)/(0.178*n**1.5)
            # but the number of possible links is n*(n-1) not n**2 and in the qscore code in benchmark.py also appears n*(n-1)
            quality_val = (cut_count - n*(n-1)/8)/(0.178*n**1.5)
        return quality_val
    
    def evaluate(self, solution: (float,list)) -> (float, float):
        """
        See validate for the expected format of the solution.
        """
        start = time() * 1000
        if solution[1] is None:
            #take the expectation value
            cut_count = solution[0]
        else:
            cut_count = number_of_cuts(self.problem, solution[1])
        quality = self._quality(cut_count)
        #print("evaluate:", solution, cut_count, quality)
        return quality , round(time() * 1000 - start, 3) 
    
    def save(self, path: str, rep_count: int) -> None:
        nx.write_gpickle(self.problem, f"{path}/graph{rep_count}.gpickle")

    
        