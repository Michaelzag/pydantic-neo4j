import uuid
from datetime import datetime

from typing import Union
import neo4j
from pydantic import create_model

from .database_operations import DatabaseOperations
from .graph_base_models import (NodeModel,
                                RelationshipModel,
                                SequenceNodeModel,
                                SequenceQueryModel,)


class MatchUtilities:

    def __init__(self, database_operations: DatabaseOperations):
        self.database_operations = database_operations


    @staticmethod
    def get_node_prefix(node_name: str, node_prefix: str) -> str:
        if node_name != "":
            node_query = f"{node_prefix}:{node_name}"
        else:
            node_query = node_prefix
        return node_query

    @staticmethod
    def build_criteria_string(
            criteria: Union[dict, None], criteria_type: str, prefix: str
    ) -> str:
        criteria_string = ""
        if criteria is not None and criteria != {}:
            if criteria_type == "node":
                criteria_string = f"{{{DatabaseOperations.get_node_criteria_string(criteria, prefix)}}}"
            elif criteria_type == "relationship":
                criteria_string = f"{{{DatabaseOperations.get_relationship_criteria_string(criteria, prefix)}}}"
        return criteria_string

    @staticmethod
    def get_model_spec(element: neo4j.graph) -> dict:
        model_spec = {key: (type(value), ...) for key, value in element.items()}
        if "created_at" in model_spec:
            model_spec["created_at"] = (datetime, ...)
        if "updated_at" in model_spec:
            model_spec["updated_at"] = (datetime, ...)
        return model_spec

    def get_node_model(self, element: neo4j.graph) -> Union[NodeModel | None]:
        labels = [label for label in element.labels]
        model_spec = self.get_model_spec(element)

        model = create_model(labels[0], __base__=NodeModel, **model_spec)
        return model(**dict(element))

    def get_relationship_model(
            self, element: neo4j.graph.Relationship
    ) -> RelationshipModel:
        model_spec = self.get_model_spec(element)
        # model_spec = {key: (type(value), ...) for key, value in element.items()}
        start_node = None
        end_node = None
        if element.start_node is not None:
            start_node = self.get_node_model(element.start_node)
            model_spec["start_node"] = (start_node.__class__, ...)
        if element.end_node is not None:
            end_node = self.get_node_model(element.end_node)
            model_spec["end_node"] = (end_node.__class__, ...)

        label = element.type
        model = create_model(label, __base__=RelationshipModel, **model_spec)
        return model(start_node=start_node, end_node=end_node, **dict(element))

    async def node_query(
            self,
            node_name: str = "",
            criteria: dict = None,
            node_prefix: str = "n",
            with_return: bool = True,
            statement: str = "MATCH",
    ) -> dict[uuid.UUID, NodeModel]:
        criteria_string = self.build_criteria_string(
            criteria=criteria, prefix=node_prefix, criteria_type="node"
        )
        node_query = self.get_node_prefix(node_name, node_prefix)
        node_models = {}

        query = f"{statement} ({node_query} {criteria_string})"
        if with_return:
            query += f" RETURN {node_prefix}"

        eager_result = await self.database_operations.run_query(query)
        for record in eager_result.records:
            node = self.get_node_model(record[node_prefix])
            node_models[node.graph_id] = node

        return node_models

    async def relationship_query(
            self,
            start_node_name: str = "",
            start_criteria: dict = None,
            start_node_prefix: str = "n",
            end_node_name: str = "",
            end_criteria: dict = None,
            end_node_prefix: str = "m",
            relationship_name: str = "",
            relationship_criteria: dict = None,
            relationship_prefix: str = "r",
            with_return: bool = True,
    ) -> dict[uuid.UUID, RelationshipModel]:
        start_criteria_string = self.build_criteria_string(
            criteria=start_criteria, prefix=start_node_prefix, criteria_type="node"
        )

        start_node_query = self.get_node_prefix(start_node_name, start_node_prefix)
        start_node = f"({start_node_query} {start_criteria_string})"

        relationship_criteria_string = self.build_criteria_string(
            criteria=relationship_criteria,
            prefix=relationship_prefix,
            criteria_type="relationship",
        )
        relationship_query_string = self.get_node_prefix(
            relationship_name, relationship_prefix
        )
        relationship = f"-[{relationship_query_string} {relationship_criteria_string}]-"

        end_criteria_string = self.build_criteria_string(
            criteria=end_criteria, prefix=end_node_prefix, criteria_type="node"
        )
        end_node_query = self.get_node_prefix(end_node_name, end_node_prefix)
        end_node = f"({end_node_query} {end_criteria_string})"

        relationship_models = {}
        # todo: Build more complex queries
        query = f"MATCH {start_node}{relationship}{end_node}"
        if with_return:
            query += (
                f" RETURN {start_node_prefix}, {relationship_prefix}, {end_node_prefix}"
            )

        eager_result = await self.database_operations.run_query(query)
        # node_types = set()
        for record in eager_result.records:
            # todo: nodes can have multiple labels, I havent found a case where I would need to do this yet

            for element in record:
                if type(element) == neo4j.graph.Node:
                    pass
                elif type(element) == neo4j.graph.Path:
                    pass
                else:
                    try:
                        rel_model = self.get_relationship_model(element)
                        if rel_model.graph_id not in relationship_models:
                            relationship_models[rel_model.graph_id] = rel_model
                    except Exception as e:
                        print(e)

        return relationship_models

    async def sequence_query(
            self, sequence_query: SequenceQueryModel
    ) -> SequenceNodeModel:
        rel_models = {}
        node_models = {}
        if (
                len(sequence_query.node_sequence)
                - len(sequence_query.relationship_sequence)
                != 1
        ):
            raise ValueError("Each relationship must have a start and end node")
        node_iter = iter(sequence_query.node_sequence)
        rel_iter = iter(sequence_query.relationship_sequence)
        index = 0
        query = "MATCH "
        returns = ""
        while index < len(sequence_query.relationship_sequence):
            node = next(node_iter)

            node_prefix = ""
            if node.include_with_return:
                node_prefix = DatabaseOperations.get_random_prefix()
            node_criteria_string = self.build_criteria_string(
                criteria=node.criteria, prefix=node_prefix, criteria_type="node"
            )
            node_query = self.get_node_prefix(node.name, node_prefix)
            node_string = f"({node_query} {node_criteria_string})"

            relationship = next(rel_iter)
            relationship_prefix = ""
            if relationship.include_with_return:
                relationship_prefix = DatabaseOperations.get_random_prefix()

            relationship_criteria_string = self.build_criteria_string(
                criteria=relationship.criteria,
                prefix=relationship_prefix,
                criteria_type="relationship",
            )

            relationship_query_string = self.get_node_prefix(
                relationship.name, relationship_prefix
            )

            relationship_string = (
                f"-[{relationship_query_string} {relationship_criteria_string}]-"
            )

            query += f"{node_string}{relationship_string}"
            if node.include_with_return:
                returns += f"{node_prefix}, "
            if relationship.include_with_return:
                returns += f"{relationship_prefix}, "
            index += 1

        node = next(node_iter)
        node_prefix = ""
        if node.include_with_return:
            node_prefix = DatabaseOperations.get_random_prefix()
        node_criteria_string = self.build_criteria_string(
            criteria=node.criteria, prefix=node_prefix, criteria_type="node"
        )
        node_query = self.get_node_prefix(node.name, node_prefix)
        node_string = f"({node_query} {node_criteria_string})"
        query += node_string

        if node.include_with_return or len(returns) == 0:
            returns += f"{node_prefix}, "
        return_string = f" RETURN {returns}"
        returns_string = return_string[:-2]
        query += returns_string

        eager_result = await self.database_operations.run_query(query)
        for record in eager_result.records:
            for element in record:
                if type(element) == neo4j.graph.Node:
                    try:
                        node_model = self.get_node_model(element)
                        if node_model.graph_id not in node_models:
                            node_models[node_model.graph_id] = node_model

                    except Exception as e:
                        print(f"Node add Error: {e}")
                elif type(element) == neo4j.graph.Path:
                    pass
                else:
                    try:
                        rel_model = self.get_relationship_model(element)
                        if rel_model.graph_id not in rel_models:
                            rel_models[rel_model.graph_id] = rel_model
                    except Exception as e:
                        print(f"Relationship add Error: {e}")

        sequence_return_model = SequenceNodeModel(
            nodes=node_models, relationships=rel_models
        )
        return sequence_return_model
