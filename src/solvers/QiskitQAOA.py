#  Copyright 2021 The QUARK Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from typing import Tuple
from typing import TypedDict

import numpy as np
from qiskit import Aer
from qiskit.algorithms import VQE, QAOA, NumPyMinimumEigensolver
from qiskit.algorithms.optimizers import POWELL, SPSA, COBYLA
from qiskit.circuit.library import TwoLocal
from qiskit.opflow import PauliSumOp
from qiskit_optimization.applications import OptimizationApplication

from devices.HelperClass import HelperClass
from solvers.Solver import *


class QiskitQAOA(Solver):
    """
    Qiskit QAOA.
    """

    def __init__(self):
        """
        Constructor method
        """
        super().__init__()
        self.device_options = ["qasm_simulator", "qasm_simulator_gpu"]

    def get_device(self, device_option: str) -> HelperClass:
        if device_option == "qasm_simulator":
            return HelperClass("qasm_simulator")
        elif device_option == "qasm_simulator_gpu":
            return HelperClass("qasm_simulator_gpu")
        else:
            raise NotImplementedError(f"Device Option {device_option} not implemented")

    def get_parameter_options(self) -> dict:
        """
        Returns the configurable settings for this solver.

        :return:
                 .. code-block:: python

                              return {
                                        "shots": {  # number measurements to make on circuit
                                            "values": list(range(10, 500, 30)),
                                            "description": "How many shots do you need?"
                                        },
                                        "iterations": {  # number measurements to make on circuit
                                            "values": [10, 20, 50, 75],
                                            "description": "How many iterations do you need?"
                                        },
                                        "depth": {
                                            "values": [2, 3, 4, 5, 10, 20],
                                            "description": "How many layers for QAOA (Parameter: p) do you want?"
                                        },
                                        "method": {
                                            "values": ["classic", "vqe", "qaoa"],
                                            "description": "Which Qiskit solver should be used?"
                                        },
                                        "optimizer": {
                                            "values": ["POWELL", "SPSA", "COBYLA"],
                                            "description": "Which Qiskit solver should be used?"
                                        }
                                    }

        """
        return {
            "shots": {  # number measurements to make on circuit
                "values": list(range(10, 500, 30)),
                "description": "How many shots do you need?"
            },
            "iterations": {  # number measurements to make on circuit
                "values": [10, 20, 50, 75],
                "description": "How many iterations do you need?"
            },
            "depth": {
                "values": [2, 3, 4, 5, 10, 20],
                "description": "How many layers for QAOA (Parameter: p) do you want?"
            },
            "method": {
                "values": ["classic", "vqe", "qaoa"],
                "description": "Which Qiskit solver should be used?"
            },
            "optimizer": {
                "values": ["POWELL", "SPSA", "COBYLA"],
                "description": "Which Qiskit solver should be used?"
            }
        }

    class Config(TypedDict):
        """
        Attributes of a valid config.

        .. code-block:: python

            shots: int
            depth: int
            iterations: int
            layers: int
            method: str

        """
        shots: int
        depth: int
        iterations: int
        layers: int
        method: str

    @staticmethod
    def normalize_data(data: any, scale: float = 1.0) -> any:
        """
        Not used currently, as I just scale the coefficients in the qaoa_operators_from_ising.

        :param data:
        :type data: any
        :param scale:
        :type scale: float
        :return: scaled data
        :rtype: any
        """
        return scale * data / np.max(np.abs(data))

    def run(self, mapped_problem: any, device_wrapper: any, config: Config, **kwargs: dict) -> (any, float):
        """
        Run Qiskit QAOA algorithm on Ising.

        :param mapped_problem: dictionary with the keys 'J' and 't'
        :type mapped_problem: any
        :param device_wrapper: instance of device
        :type device_wrapper: any
        :param config:
        :type config: Config
        :param kwargs: no additionally settings needed
        :type kwargs: any
        :return: Solution, the time it took to compute it and optional additional information
        :rtype: tuple(list, float, dict)
        """

        J = mapped_problem['J']
        t = mapped_problem['t']
        start = time() * 1000
        ising_op = self._get_pauli_op((t, J))
        if config["method"] == "classic":
            algorithm = NumPyMinimumEigensolver()
        else:
            optimizer = None
            if config["optimizer"] == "COBYLA":
                optimizer = COBYLA(maxiter=config["iterations"])
            elif config["optimizer"] == "POWELL":
                optimizer = POWELL(maxiter=config["iterations"])
            elif config["optimizer"] == "SPSA":
                optimizer = SPSA(maxiter=config["iterations"])
            if config["method"] == "vqe":
                ry = TwoLocal(ising_op.num_qubits, "ry", "cz", reps=config["depth"], entanglement="full")
                algorithm = VQE(ry, optimizer=optimizer, quantum_instance=self._get_quantum_instance(device_wrapper))
            elif config["method"] == "qaoa":
                algorithm = QAOA(reps=config["depth"], optimizer=optimizer,
                                 quantum_instance=self._get_quantum_instance(device_wrapper))

        # run actual optimization algorithm
        result = algorithm.compute_minimum_eigenvalue(ising_op)
        best_bitstring = self._get_best_solution(result)
        return best_bitstring, round(time() * 1000 - start, 3), {}

    @staticmethod
    def _get_quantum_instance(device_wrapper: any) -> any:
        backend = Aer.get_backend("qasm_simulator")
        if device_wrapper.device == 'qasm_simulator_gpu':
            logging.info("Using GPU simulator")
            backend.set_options(device='GPU')
            backend.set_options(method='statevector_gpu')
        else:
            logging.info("Using CPU simulator")
            backend.set_options(device='CPU')
            backend.set_options(method='statevector')
            backend.set_options(max_parallel_threads=48)
        return backend

    @staticmethod
    def _get_best_solution(result: any) -> any:
        best_bitstring = OptimizationApplication.sample_most_likely(result.eigenstate)
        return best_bitstring

    @staticmethod
    def _get_pauli_op(ising: Tuple[np.ndarray, np.ndarray]) -> object:
        pauli_list = []
        number_qubits = len(ising[0])

        # linear terms
        it = np.nditer(ising[0], flags=['multi_index'])
        for x in it:
            logging.debug("{:.2f} <{}>".format(x, it.multi_index))
            key = it.multi_index[0]
            pauli_str = "I" * number_qubits
            pauli_str_list = list(pauli_str)
            pauli_str_list[(key)] = "Z"
            pauli_str = "".join(pauli_str_list)
            pauli_list.append((pauli_str, complex(x)))

        # J Part with 2-Qubit interactions
        it = np.nditer(ising[1], flags=['multi_index'])
        for x in it:
            logging.debug("{:.2f} <{} >".format(x, it.multi_index))
            idx1 = it.multi_index[0]
            idx2 = it.multi_index[1]
            pauli_str = "I" * number_qubits
            pauli_str_list = list(pauli_str)
            pauli_str_list[(idx1)] = "Z"
            pauli_str_list[(idx2)] = "Z"
            pauli_str = "".join(pauli_str_list)
            pauli_list.append((pauli_str, complex(x)))

        # for key, value in ising[0].items():
        #     pauli_str = "I"*number_qubits
        #     pauli_str_list = list(pauli_str)
        #     pauli_str_list[key] = "Z"
        #     pauli_str = "".join(pauli_str_list)
        #     pauli_list.append((pauli_str, value))
        #
        # for key, value in ising[1].items():
        #     pauli_str = "I"*number_qubits
        #     pauli_str_list = list(pauli_str)
        #     pauli_str_list[key[0]] = "Z"
        #     pauli_str_list[key[1]] = "Z"
        #     pauli_str = "".join(pauli_str_list)
        #     pauli_list.append((pauli_str, value))

        isingOp = PauliSumOp.from_list(pauli_list)
        return isingOp
