from collections import defaultdict, deque

from pipeline.core.base_stage import BaseStage


class DagScheduler:
    def schedule(self, stages: list[type[BaseStage]]) -> list[list[type[BaseStage]]]:
        graph = defaultdict(set)
        for stage in stages:
            for dep in stage.depends_on:
                graph[dep].add(stage)

        indegree = defaultdict(int)
        for stage in stages:
            indegree[stage] = 0
        for neighbours in graph.values():
            for neighbour in neighbours:
                indegree[neighbour] += 1

        queue = deque([node for node, degree in indegree.items() if degree == 0])
        ordered_stages: list[list[type[BaseStage]]] = []

        while queue:
            level_size = len(queue)
            ordered_stages.append([])
            for _ in range(level_size):
                node = queue.popleft()
                ordered_stages[-1].append(node)
                for neighbour in graph[node]:
                    indegree[neighbour] -= 1
                    if indegree[neighbour] == 0:
                        queue.append(neighbour)

        if sum(len(level) for level in ordered_stages) != len(stages):
            raise ValueError("Cycle detected in DAG")

        return ordered_stages
