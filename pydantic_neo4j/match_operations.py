import uuid
from datetime import datetime

from typing import Union, Type
import neo4j
from pydantic import create_model

from .database_operations import DatabaseOperations, NeoObjectType
from .graph_base_models import (NodeModel,
                                RelationshipModel,
                                SequenceNodeModel,
                                SequenceQueryModel, SequenceCriteriaModel, SequenceCriteriaRelationshipModel,
                                SequenceCriteriaNodeModel, )


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
            criteria: Union[dict, None], criteria_type: NeoObjectType, prefix: str
    ) -> str:
        criteria_string = ""
        if criteria is not None and criteria != {}:
            if criteria_type == NeoObjectType.NODE:
                criteria_string = f"{{{DatabaseOperations.get_node_criteria_string(criteria, prefix)}}}"
            elif criteria_type == NeoObjectType:
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

    @staticmethod
    def get_sequence_criteria(criteria_model: SequenceCriteriaModel,
                              neo_object: NeoObjectType
                              ) -> tuple[str, str]:

        prefix = ""
        if criteria_model.include_with_return:
            prefix = f"{DatabaseOperations.get_random_prefix()}"
        obj_string = MatchUtilities.get_node_prefix(criteria_model.name, prefix)
        criteria_string = MatchUtilities.build_criteria_string(criteria=criteria_model.criteria,
                                                               prefix=prefix,
                                                               criteria_type=neo_object)

        if type(criteria_model) == SequenceCriteriaRelationshipModel:
            from_symbol = criteria_model.from_symbol
            to_symbol = criteria_model.to_symbol
            return prefix, f"{from_symbol}[{obj_string} {criteria_string}]{to_symbol}"

        return prefix, f"({obj_string} {criteria_string})"

    @staticmethod
    def build_sequence_query_string(sequence_query: SequenceQueryModel, keyword: str = 'MATCH') -> str:
        return_prefixes = []
        start_node = sequence_query.node_sequence.pop(0)
        start_node_prefix, start_node_string = MatchUtilities.get_sequence_criteria(start_node,
                                                                                    NeoObjectType.NODE)

        if start_node.include_with_return:
            return_prefixes.append(start_node_prefix)

        sequence_query_string = f"{keyword} {start_node_string}"

        # for relationship in sequence_query.relationship_sequence:
        while sequence_query.relationship_sequence:
            relationship = sequence_query.relationship_sequence.pop(0)
            relationship_prefix, relationship_string = MatchUtilities.get_sequence_criteria(relationship,
                                                                                            NeoObjectType.RELATIONSHIP)

            if relationship.include_with_return:
                return_prefixes.append(relationship_prefix)

            sequence_query_string += relationship_string

            next_node = sequence_query.node_sequence.pop(0)
            next_node_prefix, next_node_string = MatchUtilities.get_sequence_criteria(next_node,
                                                                                      NeoObjectType.NODE)

            if next_node.include_with_return:
                return_prefixes.append(next_node_prefix)

            sequence_query_string += next_node_string

        if return_prefixes:
            sequence_query_string = f"{sequence_query_string} RETURN "
            for prefix in return_prefixes:
                sequence_query_string += f"{prefix}, "
            sequence_query_string = sequence_query_string[:-2]
        return sequence_query_string

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
            criteria=criteria, prefix=node_prefix, criteria_type=NeoObjectType.NODE
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

    async def sequence_query(self,
                             sequence_query: SequenceQueryModel
                             ) -> SequenceNodeModel:

        rel_models = {}
        node_models = {}
        if (
                len(sequence_query.node_sequence)
                - len(sequence_query.relationship_sequence)
                != 1
        ):
            raise ValueError("Each relationship must have a start and end node")

        query = MatchUtilities.build_sequence_query_string(sequence_query)

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

    async def relationship_query(self,
                                 start_node_name: str = "",
                                 start_criteria: dict = None,
                                 end_node_name: str = "",
                                 end_criteria: dict = None,
                                 relationship_name: str = "",
                                 relationship_criteria: dict = None
                                 ) -> dict[uuid.UUID, RelationshipModel]:
        start_node = SequenceCriteriaNodeModel(name=start_node_name,
                                               criteria=start_criteria,
                                               include_with_return=True)
        end_node = SequenceCriteriaNodeModel(name=end_node_name,
                                             criteria=end_criteria,
                                             include_with_return=True)
        relationship_model = SequenceCriteriaRelationshipModel(name=relationship_name,
                                                               criteria=relationship_criteria,
                                                               include_with_return=True)
        sequence_query = SequenceQueryModel(node_sequence=[start_node, end_node],
                                            relationship_sequence=[relationship_model])
        sequence_query_string = MatchUtilities.build_sequence_query_string(sequence_query=sequence_query,
                                                                           keyword='MATCH')
        print(sequence_query_string)
        eager_result = await self.database_operations.run_query(sequence_query_string)
        rel_models = {}
        for record in eager_result.records:
            for element in record:
                print(f"element: {element}")
                if type(element) != neo4j.graph.Node and type(element) != neo4j.graph.Path:
                    print(element)
                    try:
                        rel_model = self.get_relationship_model(element)
                        if rel_model.graph_id not in rel_models:
                            rel_models[rel_model.graph_id] = rel_model
                    except Exception as e:
                        print(f"Relationship add Error: {e}")
        #print(rel_models)
        return rel_models
