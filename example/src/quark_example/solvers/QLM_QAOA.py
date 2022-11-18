
from typing import TypedDict

import networkx as nx

from devices.SimulatedAnnealingSampler import SimulatedAnnealingSampler
from solvers.Solver import *
from devices.Device import Device

from qat.lang.AQASM import Program
from qat.opt import CombinatorialProblem


import os.path
import json
from datetime import datetime


class Config(TypedDict):
    """
    Attributes of a valid config
    .. code-block:: python
         nbshots : int

    """
    nbshots : int
    
class QLM_QAOA(Solver):
    """
    QLM QAOA solver
    """

    def __init__(self):
        """
        Constructor method
        """
        super().__init__()
        self.device_options = ["myQLM"]
        self.state_sampling = "yes" # "no", "optional",        

    def get_device(self, device_option: str) -> Device:
        raise NotImplementedError("QLM_QUBO_Solver does not have default devices - you have to specify the devices within the module configuration.")


    def get_parameter_options(self) -> dict:
        """
        Returns the configurable settings for this solver

        :return:
                 .. code-block:: python
        param_options = {}
        if self.support_state_sampling:
            param_options["nbshots"] = {
                "values": [0, 100, 500, 1000],
                "description": "Number of shots for coumputing the state. 0 implies that only the energy expectation value will be computed but not the state."
            }
        param_options["depth"] = {
                "values":[1,2],
                "description": "Depth of QUAOA"
            }
 
        """
        param_options = {}
        if self.state_sampling == "yes":
            param_options["nbshots"] = {
                "values": [100, 500, 1000],
                "description": "Number of shots for computing the state."
            }
        elif self.state_sampling == "optional":
            param_options["nbshots"] = {
                "values": [0, 100, 500, 1000],
                "description": "Number of shots for computing the state. 0 implies that only the energy expectation value will be computed but not the state."
            }
        param_options["depth"] = {
                "values":[1,2],
                "description": "Depth of QUAOA"
            }
        return param_options

    def run(self, mapped_problem: dict, device_wrapper: any, config: Config, **kwargs: dict) -> (any, float):
        """
        Run QBSolv algorithm on QUBO formulation.

        :param mapped_problem: dictionary with the key 'Q' where its value should be the QUBO
        :type mapped_problem: dict
        :param device_wrapper: instance of an annealer
        :type device_wrapper: any
        :param config: annealing settings
        :type config: Config
        :param kwargs: no additionally settings needed
        :type kwargs: any
        :return: Solution and the time it took to compute it
        :rtype: tuple(dict, float)
        """
        
        start = time() * 1000

        store_dir = kwargs["store_dir"]
        i_rep = kwargs["repetition"]
        
        depth = config["depth"]
        job, keys = self.toJob(mapped_problem, depth)
    
        device = device_wrapper.get_device()
        
        qpu = device.getQPU()
        ScipyMinimizePlugin = device.get_plugin("qat.plugins:ScipyMinimizePlugin")

        beta = [0.1,0.1,0.1][0:depth]
        gamma = [-0.1,-0.1,-0.1][0:depth]

        stack = ScipyMinimizePlugin(method="COBYLA",
                            #x0 = beta + gamma,
                            tol=1e-5, 
                            options={"maxiter": 600}) | qpu   #300

        result = device.submit(stack, job)
        final_energy = result.value
        
        print("Final energy:", final_energy, f"elpased time: {int(time()*1000 - start)}s")
        #print(result.meta_data)
        
        store_file = os.path.join(store_dir,f"minimizer_meta_data_{i_rep}.json")
        logging.info(f"store result_meta_data in {store_file}")
        with open(store_file, 'w') as fh:
            json.dump(result.meta_data, fh)            

        
        nbshots = 0 if not self.state_sampling in ["yes","optional"] else config['nbshots']
        print("################nbshots",nbshots)
        solution = None
        if nbshots > 0:
            logging.info(f"Rerun job for state sampling with nbshots={nbshots}")
            #Rerunning in 'SAMPLE' mode to get the most probable states:
            #Binding the variables:
            sol_job = job(**eval(result.meta_data["parameter_map"]))
            sampling_job = sol_job.circuit.to_job(nbshots = config['nbshots'])
            sol_res = device.submit(qpu, sampling_job)
            solution = self._result_to_solution(mapped_problem, sol_res, keys, config, store_dir, i_rep)
        
        return (final_energy, solution), round(time() * 1000 - start, 3), ""
 

class QLMQuboSolv(QLM_QAOA):

    def __init__(self):
        """
        Constructor method
        """
        super().__init__()
    
        
    def quboToCP(self, qubo):
            
        cp = CombinatorialProblem()

        #assign a binary variable to each value of key.
        #The list 'keys' will be needed to later on find the key corresponding
        #to each binary variable:  bin_vars[k] corresponds to keys[k]
        keys = list(set([k1 for (k1,k2) in qubo ]))  
        n = len(keys)        
        bin_vars = cp.new_vars(n)
        
        for i in range(n):
            for j in range(n):
                weight = qubo[keys[i],keys[j]]
                if weight != 0:
                    cp.add_clause(bin_vars[i] & bin_vars[j], weight=weight)
                    
        return cp, keys

    def toJob(self, mapped_problem, depth=2):
        qubo = mapped_problem['Q']
        cp, keys = self.quboToCP(qubo)
        job = cp.qaoa_ansatz(depth)
        return job, keys

    def _state_to_QUBO(self, state, keys):
        qubo_state = {}
        n = len(keys)
        for i in range(n):
            qubo_state[keys[i]] = state[i]
        return qubo_state            
            


    def _result_to_solution(self, mapped_problem, result, keys, config : Config, store_dir, i_rep):
        qubo_result = []
        for sample in result:
            qubo_state = self._state_to_QUBO(sample.state, keys)
            qubo_result.append((qubo_state, sample.probability))    
        return qubo_result


        

