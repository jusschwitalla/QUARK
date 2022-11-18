def number_of_cuts(graph, partition):  
    """
    partition
    """    
    assert len(graph) == len(partition)
    number_of_cuts = 0
    for (u, v) in graph.edges():
        if partition[u] * partition[v] == (-1):
            number_of_cuts += 1
    return number_of_cuts


#### TESTS

import  unittest
import networkx as nx

class TestMaxCutUtils(unittest.TestCase):
    def test_number_of_cuts(self):
        G = nx.Graph()

        n=5
        for i in range(n):
            G.add_edge(i, (i+1)%n)
            
        test_cases = [([1,-1,-1,-1,-1], 2), 
                      ([1,1,-1,-1,-1], 2),
                      ([1,-1,1,-1,1], 4)]
        for partition, nbcuts_expected in test_cases:
            nbcuts = number_of_cuts(G, partition)
            self.assertEqual(nbcuts, nbcuts_expected)
        
if __name__ == '__main__':
    unittest.main()
