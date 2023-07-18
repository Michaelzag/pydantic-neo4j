from __future__ import annotations

import datetime
from typing import Optional, Dict, Union, Any

from pydantic import BaseModel, Field, ConfigDict
import uuid


class Neo4jModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    graph_id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4)
    active: Optional[bool] = Field(default=True)
    version: int = Field(default=1)
    created_at: Optional[datetime.datetime] = Field(
        default_factory=datetime.datetime.now
    )
    updated_at: Optional[datetime.datetime] = Field(
        default_factory=datetime.datetime.now
    )

    def __eq__(self, other):
        return self.node_id == other.node_id

    def get_required_fields(self) -> Dict[str, Any]:
        """Fields needed for minimum compatibility between create and match modules"""
        fields = {}
        for field, value in self.__class__.model_fields.items():
            if value.is_required():
                fields[field] = getattr(self, field)
        return fields

    def get_identifying_fields(self) -> Dict[str, Union[uuid.UUID]]:
        fields = {}
        for field, value in self.__class__.model_fields.items():
            if value.annotation == uuid.UUID or value.annotation == Optional[uuid.UUID]:
                fields[field] = getattr(self, field)
        return fields


class NodeModel(Neo4jModel):
    def get_fields(self) -> Dict[str, Any]:
        fields = {}
        for field, value in self.__class__.model_fields.items():
            fields[field] = getattr(self, field)
        return fields


class RelationshipModel(Neo4jModel):
    is_directional: bool = Field(default=True)
    start_node: Optional[NodeModel]
    end_node: Optional[NodeModel]

    def get_fields(self) -> Dict[str, Any]:
        fields = {}
        for field, value in self.__class__.model_fields.items():
            if field != "start_node" and field != "end_node":
                fields[field] = getattr(self, field)
        return fields


class RelationshipQueryModel(BaseModel):
    start_node_name: Optional[str] = Field(default="")
    start_criteria: Optional[Dict] = Field(default_factory=dict)
    end_node_name: Optional[str] = Field(default="")
    end_criteria: Optional[Dict] = Field(default_factory=dict)
    relationship_name: Optional[str] = Field(default="")
    relationship_criteria: Optional[Dict] = Field(default_factory=dict)


class SequenceCriteriaModel(BaseModel):
    name: Optional[str] = Field(default="")
    criteria: Optional[Dict] = Field(default_factory=dict)
    include_with_return: Optional[bool] = Field(default=False)


class SequenceCriteriaNodeModel(SequenceCriteriaModel):
    pass


class SequenceCriteriaRelationshipModel(SequenceCriteriaModel):
    from_symbol: str = Field(default="-")
    to_symbol: str = Field(default="-")


class SequenceQueryModel(BaseModel):
    node_sequence: Optional[list[SequenceCriteriaNodeModel]] = Field(default_factory=list)
    relationship_sequence: Optional[list[SequenceCriteriaRelationshipModel]] = Field(
        default_factory=list
    )


class SequenceNodeModel(BaseModel):
    nodes: Optional[dict[str, NodeModel]] = Field(default_factory=dict)
    relationships: Optional[dict[str, RelationshipModel]] = Field(default_factory=dict)
