

### Purpose of the Package
+ To translate from Pydantic models to Neo4j Graphs

### Getting Started
+ Install the package
```bash
pip install pydantic-neo4j
```

### Usage
+ Import the package and models
```python
from pydantic_neo4j import (PydanticNeo4j, 
                            RelationshipQueryModel,
                            NodeModel,
                            SequenceCriteriaModel, 
                            SequenceQueryModel, 
                            SequenceNodeModel)
```
+ Initialize the class and get the utilities
```python

pydantic_neo4j = PydanticNeo4j(username='neo4j', password='neo4j', uri='neo4j://localhost:7687)
match_util = pydantic_neo4j.match_utilities
create_util = pydantic_neo4j.create_utilities
database_operations = pydantic_neo4j.database_operations
```
+ Create some Pydantic models
```python
class Manufacturer(NodeModel):
    name: str

class Design(NodeModel):
    color: str
    
class Component(NodeModel):
    name: str
    
class IsOrderable(RelationshipModel):
    pass

class Produces(RelationshipModel):
    design_revision: int
```


+ Create the nodes and relationships. All relationships must have a start_node and end_node
```python
relationships = []

manufacturer = Manufacturer(name="Acme")
design = Design(color="red")
produces = Produces(design_revision=3, start_node=manufacturer, end_node=design)
```
+ Add to list
```python
relationships.append(produces)
```
+ Create another relationship and add it to the list
```python
component = Component(component_type="widget")
is_orderable = IsOrderable(start_node=design, end_node=component)

relationships.append(is_orderable)
```

+ Add the nodes and relationships to the graph
```python
await create_util.create_relationships(relationships=relationships)
````
+ Query the graph for a single node. Lets find a manufacturer
```python
nodes = await match_util.node_query(node_name='Manufacturer')

```
+ Query the graph for multiple nodes. Lets find all nodes that are active
```python
nodes = await match_util.node_query(criteria={'active': True})
```

+ Query the graph for a single relationship. Lets find a manufacturer that produces a red design
```python
query = RelationshipQueryModel(
    start_node_name="Manufacturer",
    start_criteria={},
    end_node_name="Design",
    end_criteria={"color": "red"},
    relationship_name="Produces",
    relationship_criteria={})
result = await match_util.match_relationship(query=query)
```

+ Query the graph for multiple relationships. Lets find all manufacturers that make a widget component
+ This uses a sequence, which is a series of relationships. Similar to Neo4j Path
```python
sequence_query = SequenceQueryModel()

sequence_query.node_sequence.append(SequenceCriteriaModel(name='Manufacturer'))
sequence_query.relationship_sequence.append(SequenceCriteriaModel()) # a relationship with no criteria
sequence_query.node_sequence.append(SequenceCriteriaModel() # a node with no criteria specified
sequence_query.relationship_sequence.append(SequenceCriteriaModel()) #a realtoinship with no criteria
sequence_query.node_sequence.append(SequenceCriteriaModel(component_type="widget", include_with_return=True)
```
+ The sequence query must always have 1 more node than relationship.
+ The order is important, and is a sequence. node - relationship - node - relationship - node
```python
result = await match_util.sequence_query(sequence_query=sequence_query)
```

+ Run a specific query, lets delete everything
```python
await database_operations.run_query(query=f"match (n) detach delete n")
```



### Not Implemented

+ Update a node
```python
nodes = await match_util.node_query(name='Manufacturer', criteria={name='Acme'})
for graph_id, node in nodes.items():
    node.name = "Acme2"
    await create_util.update_node(node=node)
```
+ Update a relationship
```python
    query = RelationshipQueryModel(
    start_node_name="Manufacturer",
    start_criteria={},
    end_node_name="Design",
    end_criteria={"color": "red"},
    relationship_name="Produces",
    relationship_criteria={})
    result = await match_util.match_relationship(query=query)
    for graph_id, relationship in result.items():
        relationship.design_revision = 4
        await create_util.update_relationship(relationship=relationship)
```

+ Delete a node
```python
nodes = await match_util.node_query(name='Manufacturer', criteria={name='Acme'})
for graph_id, node in nodes.items():
    await create_util.delete_node(node=node)
```

