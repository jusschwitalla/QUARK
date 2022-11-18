import logging

from quark_example.solvers.QLM_QAOA import QLM_QAOA, Config
from quark_example.max_cut.max_cut_utils import number_of_cuts


class MAX_CUT_QAOA(QLM_QAOA):

    def __init__(self):
        """
        Constructor method
        """
        super().__init__()
        self.state_sampling = "no"

    def toJob(self, mapped_problem, depth=2):
        #return mapped_problem["ising"].to_combinatorial_problem().qaoa_ansatz(depth), None  
        return mapped_problem["ising"].qaoa_ansatz(depth), None  
        
    def _state_to_solution(self, state):
        #print(state.bitstring, type(state.bitstring))
        solution_configuration = []
        for s in state.bitstring:
            solution_configuration.append(int(s)*2 - 1)
        #print(solution_configuration)
        return solution_configuration


    def _result_to_solution(self, mapped_problem, result, keys, config : Config, store_dir, i_rep):
        best_sol = None
        best_sol_prob = None
        highest_prob = 0.0
        highest_prob_sample = None
        logging.info("number of samples in result: " + str(len(result)))

        probs = []
        prob_dist = []
        num_of_cuts_max = None
        for sample in result:
            prob = sample.probability
            if prob > highest_prob:
                highest_prob_sample = sample
                highest_prob = sample.probability
            solution_configuration = self._state_to_solution(sample.state)
            num_of_cuts = number_of_cuts(mapped_problem["graph"],solution_configuration)
            if num_of_cuts_max is None or num_of_cuts_max < num_of_cuts:
                num_of_cuts_max = num_of_cuts
                best_sol = solution_configuration
                best_sol_prob = prob
            #print(sample.state, solution_configuration, sample.probability, num_of_cuts)
        print(best_sol, best_sol_prob, num_of_cuts_max)
        return best_sol