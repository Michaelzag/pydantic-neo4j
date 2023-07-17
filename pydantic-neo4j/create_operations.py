import importlib
import uuid
from typing import Type, Any

import neo4j

from .graph_base_models import NodeModel, Neo4jModel, RelationshipModel
from .database_operations import DatabaseOperations
from .match_operations import MatchUtilities


class CreateUtilities:

    def __init__(self, database_operations: DatabaseOperations, match_utilities: MatchUtilities):
        self.database_operations = database_operations
        self.match_utilities = match_utilities

    @staticmethod
    def str_to_class(model: Type[Neo4jModel], **kwargs) -> Any | None:
        """Return a class instance from a string reference"""
        try:
            module_ = importlib.import_module(model.__module__)
            class_ = getattr(module_, model.__name__)(**kwargs)
        except AttributeError:
            print(f"{model} Class does not exist")
        except ImportError:
            print("Module does not exist")
        return class_ or None

    @staticmethod
    async def get_create_node_string(model: object, node_prefix: str = "n") -> str:
        query = f"CREATE ({node_prefix}:{model.__class__.__name__}"
        criteria = DatabaseOperations.get_node_criteria_string(criteria=model.__dict__)
        if criteria != "":
            query += f" {{{criteria} }}"
        query += f") RETURN {node_prefix}"
        return query

    @staticmethod
    def get_create_relationship_string(
        start_node: NodeModel,
        end_node: NodeModel,
        relationship: RelationshipModel,
        query_term: str = "CREATE",
    ) -> str:
        start_node_prefix = "start_node"
        end_node_prefix = "end_node"
        relationship_prefix = "link"

        relationship_criteria = relationship.get_fields()

        query = DatabaseOperations.get_cypher_node_match_string(
            model=start_node.__class__,
            node_prefix=start_node_prefix,
            with_return=False,
            criteria={"graph_id": start_node.graph_id},
        )
        query += DatabaseOperations.get_cypher_node_match_string(
            model=end_node.__class__,
            node_prefix=end_node_prefix,
            with_return=False,
            criteria={"graph_id": end_node.graph_id},
        )
        criteria = DatabaseOperations.get_relationship_criteria_string(
            criteria=relationship_criteria
        )
        query += f"{query_term}({start_node_prefix}) - [{relationship_prefix}: {relationship.__class__.__name__}"
        if criteria != "":
            query += f" {{ {criteria} }}"
        arrow = "->" if relationship.is_directional else "-"
        query += f"]{arrow}({end_node_prefix}) RETURN {start_node_prefix}, {end_node_prefix}, {relationship_prefix}"

        return query

    async def create_node(self, model: NodeModel) -> NodeModel:
        # todo: add merge functionality
        # query_term = 'MERGE' if merge else 'CREATE'
        existing_node = await self.match_utilities.node_query(
            node_name=model.__class__.__name__, criteria=model.get_required_fields()
        )

        if len(existing_node) > 0:
            raise neo4j.exceptions.ClientError(f"Node already exists: {existing_node}")
        else:
            query = await self.get_create_node_string(model=model)
            eager_result = await self.database_operations.run_query(query)
            result = eager_result.records[0].data()
            return self.str_to_class(model=model.__class__, **result["n"])

    async def match_or_create_node(
        self, model: NodeModel
    ) -> tuple[uuid.UUID, NodeModel]:
        existing_node = await self.match_utilities.node_query(
            node_name=model.__class__.__name__,
            criteria=model.get_required_fields(),
            statement="MATCH",
        )

        if len(existing_node) == 0:
            new_node = await self.create_node(model=model)
            return new_node.graph_id, new_node
        elif len(existing_node) == 1:
            for key, value in existing_node.items():
                existing_node_id = key
                existing_node = value
                return existing_node_id, existing_node
        else:
            raise neo4j.exceptions.ClientError(f"Multiple nodes found: {model}")

    async def create_relationship(self, relationship: RelationshipModel):
        start_node_id, start_node = await self.match_or_create_node(
            model=relationship.start_node
        )
        end_node_id, end_node = await self.match_or_create_node(
            model=relationship.end_node
        )

        rel_exists = await self.match_utilities.relationship_query(
            start_node_name=start_node.__class__.__name__,
            start_criteria={"graph_id": start_node_id},
            end_node_name=end_node.__class__.__name__,
            end_criteria={"graph_id": end_node_id},
            relationship_name=relationship.__class__.__name__,
            relationship_criteria=relationship.get_required_fields(),
        )

        if len(rel_exists) > 0:
            # todo: make new exceptions
            raise AttributeError(
                f"Relationship already exists: {rel_exists}"
            )
        else:
            # todo: make new model based on the search results

            query = self.get_create_relationship_string(
                start_node=start_node, end_node=end_node, relationship=relationship
            )

            await self.database_operations.run_query(query)

    async def create_relationships(self, sequence: list[RelationshipModel]):
        for relationship in sequence:
            await self.create_relationship(relationship=relationship)
