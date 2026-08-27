import unittest
import torch
from knowledge_graph.train_hetero_graphsage import HeteroGraphSAGE, graph_from_training_edges, load_graph, sample_true_negatives, split_positive_edges


class HeteroGraphSageTest(unittest.TestCase):
    def test_real_neighbor_aggregation_forward_pass(self):
        data, _ = load_graph(8)
        model = HeteroGraphSAGE(data, 8)
        output = model(data)
        self.assertEqual(set(output), set(data.node_types))
        self.assertEqual(output["job"].shape, (data["job"].num_nodes, 8))
        self.assertTrue(torch.isfinite(output["skill"]).all())

    def test_held_out_edges_are_removed_from_message_passing_graph(self):
        data,_=load_graph(8);splits=split_positive_edges(data,42);train=graph_from_training_edges(data,splits)
        for edge_type,parts in splits.items():
            self.assertEqual(train[edge_type].edge_index.size(1),parts["train"].size(1))

    def test_negative_sampler_excludes_known_positive_edges(self):
        source=torch.tensor([0,0,1]);known={(0,0),(0,1),(1,2)}
        negative=sample_true_negatives(source,4,known,torch.Generator().manual_seed(42))
        self.assertTrue(all((int(s),int(t)) not in known for s,t in zip(source,negative)))


if __name__ == "__main__":
    unittest.main()
