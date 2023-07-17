from typing import Union, Type

from .database_operations import DatabaseOperations
from .graph_base_models import NodeModel, RelationshipModel
from .match_operations import MatchUtilities
from .create_operations import CreateUtilities


class PydanticNeo4j:
    _models = []
    _node_models = []
    _relationship_models = []

    def __init__(self, uri: str, username: str, password: str):
        self.database_operations = DatabaseOperations(uri=uri, username=username, password=password)
        self.match_utilities = MatchUtilities(database_operations=self.database_operations)
        self.create_utilities = CreateUtilities(database_operations=self.database_operations,
                                                match_utilities=self.match_utilities)

    def register_model(self, model: Union[Type[NodeModel], Type[RelationshipModel]]):
        self._models.append(model)
        if isinstance(model, NodeModel):
            self._node_models.append(model)
        elif isinstance(model, RelationshipModel):
            self._relationship_models.append(model)

    def register_models(self, models: list[Union[Type[NodeModel], Type[RelationshipModel]]]):
        for model in models:
            self.register_model(model)
