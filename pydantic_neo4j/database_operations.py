import datetime
import importlib
import random
import string
import uuid
from enum import Enum, auto

import neo4j

from typing import Any, Type

from .graph_base_models import Neo4jModel, NodeModel, RelationshipModel


class NeoObjectType(Enum):
    NODE = auto()
    RELATIONSHIP = auto()


class DatabaseOperations:

    def __init__(self, uri: str, username: str, password: str):
        self.driver = neo4j.AsyncGraphDatabase.driver(uri, auth=(username, password))

    async def run_query(self, query: str, **kwargs) -> neo4j.EagerResult:
        async with self.driver.session() as session:
            result = await session.run(query, **kwargs)
            eager_results = await result.to_eager_result()
        return eager_results

    @staticmethod
    def get_object_type(neo_object: Type[Neo4jModel]):
        if issubclass(neo_object, NodeModel):
            return NeoObjectType.NODE
        elif issubclass(neo_object, RelationshipModel):
            return NeoObjectType.RELATIONSHIP

    @staticmethod
    def str_to_class(model: Type[Neo4jModel], **kwargs) -> Any | None:
        """Return a class instance from a string reference"""

        try:
            module_ = importlib.import_module(model.__module__)
            # try:
            class_ = getattr(module_, model.__name__)(**kwargs)
        except AttributeError:
            print(f"{model} Class does not exist")
            return None
        except ImportError:
            print("Module does not exist")
            return None
        else:
            return class_

    @staticmethod
    def convert_value(value: Any) -> Any:
        """Wrap values in single quotes if necessary for cypher"""
        #print(f"Converting type {type(value)} -> {value}")
        if type(value) == str:
            return f"'{value}'"
        if type(value) == uuid.UUID:
            return f"'{str(value)}'"
        if type(value) == datetime.datetime:
            return f"'{str(value)}'"

        return value

    @staticmethod
    def get_node_criteria_string(
            criteria: dict, string_type: str = "attr", prefix: str = ""
    ) -> str:
        """Get the format needed for cypher query
        string_type: attt is default and returns key:value
        string_type: where will return key=value"""
        assignment = ":"
        combiner = ", "
        criteria_string = ""
        if string_type == "where":
            criteria_string = "WHERE "
            assignment = "="
            combiner = " AND "

        if prefix != "":
            prefix = f"{prefix}."

        for key, value in criteria.items():
            if value is not None:
                criteria_string += f"{prefix}{key}{assignment}{DatabaseOperations.convert_value(value)}{combiner}"

        criteria_string = criteria_string[: -len(combiner)]
        criteria_string += " "
        return criteria_string

    @staticmethod
    def get_relationship_criteria_string(
            criteria: dict, string_type: str = "attr", prefix: str = ""
    ) -> str:
        assignment = ":"
        combiner = ", "
        criteria_string = ""
        if string_type == "where":
            criteria_string = "WHERE "
            assignment = "="
            combiner = " AND "

        if prefix != "":
            prefix = f"{prefix}."

        for key, value in criteria.items():
            if value is not None:
                if key == "start_node" or key == "end_node":
                    """
                    print(value)
                    print(type(value))
                    criteria_string += DatabaseOperations.get_node_criteria_string(
                        criteria=value.get_fields(),
                        string_type=string_type,
                        prefix=prefix)
                    """
                    pass
                else:
                    criteria_string += f"{prefix}{key}{assignment}{DatabaseOperations.convert_value(value)}{combiner}"

        criteria_string = criteria_string[: -len(combiner)]
        criteria_string += " "
        return criteria_string

    @staticmethod
    def get_cypher_node_match_string(
            model: object,
            criteria: dict,
            node_prefix: str = "",
            with_return: bool = True,
            **kwargs,
    ) -> str:
        query = f"MATCH ({node_prefix}:{model.__name__}) "
        if len(kwargs) > 0:
            criteria.update(kwargs)
        if len(criteria) > 0:
            query += DatabaseOperations.get_node_criteria_string(
                criteria=criteria, prefix=node_prefix, string_type="where"
            )
        if with_return:
            query += f" RETURN {node_prefix} "
        return query

    @staticmethod
    def get_random_prefix(prefix_length: int = 4) -> str:
        return "".join(random.choices(string.ascii_lowercase, k=prefix_length))
