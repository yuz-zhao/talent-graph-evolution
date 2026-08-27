"""Unsupervised heterogeneous GraphSAGE pretraining over audited graph edges."""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import torch
import torch.nn.functional as F
from torch import nn
from torch_geometric.data import HeteroData
from torch_geometric.nn import HeteroConv, SAGEConv

BASE = Path(__file__).resolve().parent
DATASET = BASE / "gnn_dataset"
MODEL_DIR = BASE / "gnn_models"


def split_positive_edges(data, seed=42, validation_ratio=.1, test_ratio=.1):
    generator = torch.Generator().manual_seed(seed)
    result = {}
    for edge_type, edge_index in data.edge_index_dict.items():
        if edge_type[1].startswith("rev_"):
            continue
        count = edge_index.size(1); order = torch.randperm(count, generator=generator)
        test_n = int(count * test_ratio) if count >= 10 else 0
        validation_n = int(count * validation_ratio) if count >= 10 else 0
        result[edge_type] = {
            "test": edge_index[:, order[:test_n]],
            "validation": edge_index[:, order[test_n:test_n + validation_n]],
            "train": edge_index[:, order[test_n + validation_n:]],
        }
    return result


def graph_from_training_edges(data, splits):
    graph = data.clone()
    for edge_type, parts in splits.items():
        source, relation, target = edge_type
        graph[edge_type].edge_index = parts["train"]
        graph[(target, f"rev_{relation}", source)].edge_index = parts["train"].flip(0)
    return graph


def sample_true_negatives(source, target_type_size, positive_lookup, generator):
    negatives = []
    for source_id in source.tolist():
        for _ in range(100):
            candidate = int(torch.randint(0, target_type_size, (1,), generator=generator))
            if (source_id, candidate) not in positive_lookup:
                negatives.append(candidate); break
        else:
            negatives.append((candidate + 1) % target_type_size)
    return torch.tensor(negatives, dtype=torch.long)


def ranking_metrics(embeddings, edge_type, positives, all_positive, target_size, seed=42):
    if positives.size(1) == 0:
        return None
    source_type, _, target_type = edge_type; generator = torch.Generator().manual_seed(seed)
    lookup = set(zip(all_positive[0].tolist(), all_positive[1].tolist()))
    negative = sample_true_negatives(positives[0], target_size, lookup, generator)
    positive_scores = (embeddings[source_type][positives[0]] * embeddings[target_type][positives[1]]).sum(-1)
    negative_scores = (embeddings[source_type][positives[0]] * embeddings[target_type][negative]).sum(-1)
    auc = float(((positive_scores[:,None] > negative_scores[None,:]).float().mean()).item())
    scores = torch.cat([positive_scores, negative_scores]); labels = torch.cat([torch.ones_like(positive_scores), torch.zeros_like(negative_scores)])
    order = torch.argsort(scores, descending=True); precision = torch.cumsum(labels[order],0) / torch.arange(1,len(order)+1)
    ap = float((precision * labels[order]).sum().item() / max(1, int(labels.sum())))
    ranks=[]
    for index in range(positives.size(1)):
        candidates=torch.randperm(target_size,generator=generator)[:min(99,target_size)]
        if positives[1,index] not in candidates:candidates=torch.cat([positives[1,index:index+1],candidates])
        candidate_scores=embeddings[target_type][candidates] @ embeddings[source_type][positives[0,index]]
        rank=int((candidate_scores > positive_scores[index]).sum())+1;ranks.append(rank)
    return {"auc":auc,"average_precision":ap,"mrr":sum(1/r for r in ranks)/len(ranks),"hits_at_10":sum(r<=10 for r in ranks)/len(ranks),"positive_edges":len(ranks)}


def load_graph(hidden: int):
    data, indexes, source_ids = HeteroData(), {}, {}
    with (DATASET / "nodes.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line); node_type = row["node_type"]
            indexes.setdefault(node_type, {})[row["source_id"]] = len(indexes.setdefault(node_type, {}))
            source_ids.setdefault(node_type, []).append(row["source_id"])
    for node_type, mapping in indexes.items():
        data[node_type].node_id = torch.arange(len(mapping))
        data[node_type].num_nodes = len(mapping)
    edge_lists = {}
    with (DATASET / "edges.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line); edge_type = (row["source_type"], row["relation"], row["target_type"])
            edge_lists.setdefault(edge_type, [[], []])
            edge_lists[edge_type][0].append(indexes[row["source_type"]][row["source_id"]])
            edge_lists[edge_type][1].append(indexes[row["target_type"]][row["target_id"]])
    # Reverse edges ensure every node type receives messages.
    for edge_type, values in list(edge_lists.items()):
        source, relation, target = edge_type
        edge_lists[(target, f"rev_{relation}", source)] = [values[1], values[0]]
    for edge_type, values in edge_lists.items():
        data[edge_type].edge_index = torch.tensor(values, dtype=torch.long)
    return data, source_ids


class HeteroGraphSAGE(nn.Module):
    def __init__(self, data, hidden=32):
        super().__init__()
        self.embeddings = nn.ModuleDict({node_type:nn.Embedding(data[node_type].num_nodes, hidden) for node_type in data.node_types})
        self.layers = nn.ModuleList()
        for _ in range(2):
            self.layers.append(HeteroConv({edge_type:SAGEConv((-1,-1), hidden) for edge_type in data.edge_types}, aggr="sum"))

    def forward(self, data):
        values = {node_type:embedding(data[node_type].node_id) for node_type, embedding in self.embeddings.items()}
        for layer in self.layers:
            updated = layer(values, data.edge_index_dict)
            values = {node_type:F.normalize(F.relu(updated.get(node_type, values[node_type])), dim=-1) for node_type in values}
        return values


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--epochs", type=int, default=20); parser.add_argument("--hidden", type=int, default=32); parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(); random.seed(args.seed); torch.manual_seed(args.seed)
    data, source_ids = load_graph(args.hidden); splits=split_positive_edges(data,args.seed); train_data=graph_from_training_edges(data,splits); model = HeteroGraphSAGE(train_data, args.hidden); optimizer = torch.optim.Adam(model.parameters(), lr=.01, weight_decay=1e-5)
    train_edges = [(edge_type, parts["train"]) for edge_type, parts in splits.items()]
    positive_lookups={edge_type:set(zip(data[edge_type].edge_index[0].tolist(),data[edge_type].edge_index[1].tolist())) for edge_type in splits}
    history = []
    for epoch in range(1, args.epochs + 1):
        model.train(); optimizer.zero_grad(); embeddings = model(train_data); losses = []
        for (source_type, _, target_type), edge_index in train_edges:
            count = edge_index.size(1)
            if not count: continue
            sample_count = min(count, 2048); choice = torch.randperm(count)[:sample_count]
            source, positive = edge_index[0, choice], edge_index[1, choice]
            negative = sample_true_negatives(source, data[target_type].num_nodes, positive_lookups[(source_type, _, target_type)], torch.Generator().manual_seed(args.seed + epoch))
            positive_score = (embeddings[source_type][source] * embeddings[target_type][positive]).sum(-1)
            negative_score = (embeddings[source_type][source] * embeddings[target_type][negative]).sum(-1)
            losses.append(-F.logsigmoid(positive_score).mean() - F.logsigmoid(-negative_score).mean())
        loss = torch.stack(losses).mean(); loss.backward(); optimizer.step(); history.append(float(loss.detach()))
        print(f"epoch={epoch} loss={history[-1]:.6f}")
    model.eval()
    with torch.no_grad(): embeddings = model(train_data)
    evaluation={}
    for index,(edge_type,parts) in enumerate(splits.items()):
        metric=ranking_metrics(embeddings,edge_type,parts["test"],data[edge_type].edge_index,data[edge_type[2]].num_nodes,args.seed+index)
        if metric:evaluation["|".join(edge_type)]=metric
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict":model.state_dict(),"hidden":args.hidden,"metadata":data.metadata()}, MODEL_DIR / "hetero_graphsage_unsupervised.pt")
    torch.save({node_type:{"source_ids":source_ids[node_type],"embeddings":values.cpu()} for node_type,values in embeddings.items()}, MODEL_DIR / "hetero_graphsage_embeddings.pt")
    report = {
        "model":"Heterogeneous GraphSAGE", "framework":"PyTorch Geometric", "training_objective":"unsupervised typed-edge reconstruction",
        "epochs":args.epochs, "hidden_dimension":args.hidden, "initial_loss":history[0], "final_loss":history[-1], "loss_decreased":history[-1] < history[0],
        "node_types":data.node_types, "edge_type_count":len(data.edge_types), "gnn_trained":True,
        "edge_split":{"method":"deterministic_relation_stratified_80_10_10","seed":args.seed,"message_passing_uses_training_edges_only":True},
        "negative_sampling":{"known_positive_edges_excluded":True,"type_constrained":True}, "held_out_test_metrics":evaluation,
        "supervised_talent_job_ranker_trained":False, "formal_matching_accuracy_eligible":False,
        "claim_scope":"graph representation pretraining only",
    }
    (MODEL_DIR / "hetero_graphsage_training_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
