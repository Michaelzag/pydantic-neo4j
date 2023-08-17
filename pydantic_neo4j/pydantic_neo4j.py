from typing import Union, Type

from .database_operations import DatabaseOperations
from .graph_base_models import NodeModel, RelationshipModel, Neo4jModel
from .match_operations import MatchUtilities
from .create_operations import CreateUtilities


class PydanticNeo4j:
    models = []
    node_models = []
    relationship_models = []

    def __init__(self, uri: str, username: str, password: str):
        self.database_operations = DatabaseOperations(uri=uri, username=username, password=password)
        self.match_utilities = MatchUtilities(database_operations=self.database_operations)
        self.create_utilities = CreateUtilities(database_operations=self.database_operations,
                                                match_utilities=self.match_utilities)

    def register_model(self, model: Type[Neo4jModel]):
        self.models.append(model)
        if isinstance(model, NodeModel):
            self.node_models.append(model)
        elif isinstance(model, RelationshipModel):
            self.relationship_models.append(model)

    def register_models(self, models: list[Type[Neo4jModel]]):
        for model in models:
            self.register_model(model)

    def get_pydantic_model(self, model_name: str) -> Union[Type[NodeModel], Type[RelationshipModel]]:
        for model in self.models:
            if model.__name__ == model_name:
                return model
