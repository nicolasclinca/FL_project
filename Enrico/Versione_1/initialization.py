# nuova inizializzazione per il sistema RAG
from neo4j import AsyncDriver

from Enrico.Versione_1.automatic_queries import *
from Enrico.Versione_1.neo4j_handler import Neo4jHandler

### GRAPH SCHEMA ###

house_schema = """
    Node Labels and their primary properties (nodes often have multiple labels due to class hierarchy):
    Note: Ontology classes are prefixed with 'ns0__'. For example, a Room is labeled :ns0__Room.
    - ns0__Room: Represents locations. Examples: "Living_room", "Kitchen", "Bedroom", "Bathroom", "Study".
    - ns0__Device: Base label for all devices.
        - ns0__Togglable_device (subclass of ns0__Device): Has a 'ns0__state' property (string, e.g., "on", "off").
            - ns0__Light (subclass of ns0__Togglable_device): Represents all lights.
                - ns0__Dimmable_light (subclass of ns0__Light and ns0__Settable_device): Also has 'ns0__setting' (number, brightness percentage) and 'ns0__unit' ("percent"). Examples: "Ceiling_light_1", "Lamp_1", "Lamp_2".
            - ns0__Appliance (subclass of ns0__Togglable_device): Represents household appliances.
                - ns0__Air_conditioner (subclass of ns0__Appliance and ns0__Settable_device): Has 'ns0__state', 'ns0__setting' (number, temperature), and 'ns0__unit' ("C"). Examples: "Air_conditioner_1", "Air_conditioner_2".
                - ns0__Coffee_machine (subclass of ns0__Appliance): Has 'ns0__state'. Example: "Coffee_machine_1".
                - ns0__Oven (subclass of ns0__Appliance and ns0__Settable_device): Has 'ns0__state', 'ns0__setting' (number, temperature), and 'ns0__unit' ("C"). Example: "Oven_1".
                - ns0__Robot_vacuum (subclass of ns0__Appliance): Has 'ns0__state'. Example: "Robot_vacuum_1".
                - ns0__Television (subclass of ns0__Appliance): Has 'ns0__state'. Example: "Television_1".
                - ns0__Washing_machine (subclass of ns0__Appliance): Has 'ns0__state'. Example: "Washing_machine_1".
        - ns0__Settable_device (subclass of ns0__Device): Has 'ns0__setting' (varying type) and 'ns0__unit' (string) properties.
        - ns0__Sensor (subclass of ns0__Device): Has a 'ns0__value' property (varying type) and possibly 'ns0__unit'.
            - ns0__Boolean_sensor (subclass of ns0__Sensor): 'ns0__value' is boolean (true/false).
                - ns0__Occupancy_sensor: Examples: "Occupancy_sensor_1" through "Occupancy_sensor_5".
                - ns0__Smoke_sensor: Example: "Smoke_sensor_1".
            - ns0__Categorical_sensor (subclass of ns0__Sensor): 'ns0__value' is a string category.
                - ns0__Brightness_sensor: 'ns0__value' (string, e.g., "low"). Example: "Brightness_sensor_1".
            - ns0__Numeric_sensor (subclass of ns0__Sensor): 'ns0__value' is numeric.
                - ns0__Humidity_sensor: 'ns0__value' (number), 'ns0__unit' ("percent"). Example: "Humidity_sensor_1".
                - ns0__Temperature_sensor: 'ns0__value' (number), 'ns0__unit' ("C"). Example: "Temperature_sensor_1".
    """  # schema della casa

graph_schema = """
    Node Identification:
    - Individual entities (devices, rooms, sensors like 'Lamp_1', 'Kitchen') are nodes, each having a unique 'uri' property (e.g., "http://swot.sisinflab.poliba.it/home#Lamp_1").
    - These individual nodes are typically labeled with `:Resource` and `:owl__NamedIndividual`.
    - Some individuals, like Rooms, might also directly have their specific type label (e.g., a node for 'Kitchen' might be labeled `:ns0__Room`).
    - For other individuals (especially devices and sensors), their specific ontological type (e.g., Light, Temperature_sensor) might not be a direct label on the instance node. Their type is often defined by relationships (like `rdf:type`) to class nodes or inferred from the properties they possess.
    - The unique identifier for an entity (e.g., "Lamp_1", "Living_room") is the fragment part of its 'uri' (the part after '#').
    - To match a specific named individual like "Lamp_1", query its 'uri' property (e.g., `WHERE n.uri ENDS WITH '#Lamp_1'`). Do NOT assume specific type labels like `:ns0__Light` are present on these individual device/sensor nodes when matching them by URI.

    Relationship Types:
    - (Individual Device/Sensor)-[:ns0__located_in]->(Individual Room, e.g., node labeled :ns0__Room).
    - (Individual Room, e.g., node labeled :ns0__Room)-[:ns0__contains]->(Individual Device/Sensor).
    """  # schema con nodi e relazioni

example_schema = """
    Common Data Properties on Nodes (as per ontology mapping):
    Note: Data properties are also prefixed with 'ns0__'.
    - 'ns0__state': For ns0__Togglable_device instances, indicates if it's "on" or "off".
    - 'ns0__setting': For ns0__Settable_device instances, the current setting value.
    - 'ns0__unit': The unit for 'ns0__setting' or 'ns0__value' (e.g., "percent", "C").
    - 'ns0__value': For ns0__Sensor instances, the sensed value.

    Example Cypher Queries based on this schema:
    - To find if "Lamp_1" is on:
      MATCH (d) WHERE d.uri ENDS WITH "#Lamp_1" RETURN d.ns0__state AS state
    - To find the temperature setting of "Air_conditioner_1":
      MATCH (d) WHERE d.uri ENDS WITH "#Air_conditioner_1" RETURN d.ns0__setting AS setting, d.ns0__unit AS unit
    - To find what room "Lamp_1" is in:
      MATCH (d)-[:ns0__located_in]->(r:ns0__Room) WHERE d.uri ENDS WITH "#Lamp_1" RETURN r.uri AS room_uri
    - To list all devices in the "Kitchen":
      MATCH (r:ns0__Room)-[:ns0__contains]->(d) WHERE r.uri ENDS WITH "#Kitchen" RETURN d.uri AS device_uri, labels(d) AS types
    - To get the value of "Occupancy_sensor_3":
      MATCH (s) WHERE s.uri ENDS WITH "#Occupancy_sensor_3" RETURN s.ns0__value AS value
    """  # schema con regole e alcuni esempi


def select_schema(selector: str):
    selector = list(selector.upper())
    schema = f""""""

    if "H" in selector:
        schema += house_schema
    if "G" in selector:
        schema += graph_schema
    if "E" in selector:
        schema += example_schema

    return schema


### QUERY PROMPT ###

zero_prompt = f"""
    You are an expert Cypher query generator.
    Your task is to generate a Cypher query that retrieves information from a Neo4j graph database to answer the user's question.
    The graph schema is as follows:

    """

instruction_prompt = f"""

    Instructions:
    - Only output a valid Cypher query.
    - Do not include any explanations, comments, or markdown formatting like ```cypher ... ```.
    - Ensure the query returns data that can directly answer the user's question.
    - When querying a specific named individual (e.g., "Lamp 1", "Kitchen"), match it using its `uri` property (e.g., `WHERE individual.uri ENDS WITH '#Lamp_1'`). Do NOT add specific type labels like `:ns0__Light` or `:ns0__Device` to the individual node in the MATCH pattern, as these individuals are primarily labeled `:owl__NamedIndividual`.
    - However, if you are matching a Room individual, you CAN use the `:ns0__Room` label (e.g., `(r:ns0__Room)`).
    - Data properties (like `ns0__state`, `ns0__setting`, `ns0__value`) are directly on these individual nodes. Refer to the schema to know which conceptual type has which properties. The base URI for individuals is typically 'http://swot.sisinflab.poliba.it/home'.

    """

example_prompt = f"""

    For example:
    User query: "Is Lamp 1 on?"
    Appropriate Cypher query: MATCH (d) WHERE d.uri ENDS WITH '#Lamp_1' RETURN d.ns0__state AS state

    User query: "What is the temperature in the kitchen?"
    Appropriate Cypher query: MATCH (s)-[:ns0__located_in]->(r:ns0__Room) WHERE s.uri ENDS WITH '#Temperature_sensor_1' AND r.uri ENDS WITH '#Kitchen' RETURN s.ns0__value AS value, s.ns0__unit AS unit
    (Alternative for "temperature in the kitchen" if a specific sensor isn't named: MATCH (r:ns0__Room)-[:ns0__contains]->(s:ns0__Temperature_sensor) WHERE r.uri ENDS WITH '#Kitchen' RETURN s.ns0__value, s.ns0__unit. This assumes Temperature_sensor_1 is a :ns0__Temperature_sensor, which might be a class node or an individual with that label if import was different. For now, prioritize matching individuals by URI if named.)

    User query: "Which devices are in the living room?"
    Appropriate Cypher query: MATCH (r:ns0__Room)-[:ns0__contains]->(d) WHERE r.uri ENDS WITH '#Living_room' RETURN d.uri AS device_uri
    """

ans_pmt_0 = """ 
    You are a helpful assistant.
    Respond to the user in a conversational and natural way.
    Use the provided Cypher query and its output to answer the original user's question.
    Explain the information found in the database.
    If the query output is empty or does not seem to directly answer the question, state that the information could not be found or is inconclusive.
    Do not mention the Cypher query in your response unless it's crucial for explaining an error or ambiguity.
    Be concise and clear.
    """

def select_prompt(selector: str, schema: str):
    selector = list(selector.upper())
    prompt = zero_prompt + schema

    if "I" in selector:
        prompt += instruction_prompt
    if "E" in selector:
        prompt += example_prompt

    return prompt


def select_answer(selector: str = "S"):
    selector = list(selector.upper())
    if "S" in selector:  # simple
        return ans_pmt_0
    else:  # answer prompt più complessi
        return ans_pmt_0


def simple_init(schema_sel: str, prompt_sel: str, ans_sel: str) -> tuple[str, str]:
    query_prompt = select_prompt(prompt_sel, select_schema(schema_sel))
    ans_prompt = select_answer(ans_sel)
    return query_prompt, ans_prompt


async def complex_init(handler: Neo4jHandler, schema_sel: str = 'ghe',
                       prompt_sel: str = 'ei', ans_sel: str = 's') -> tuple[str, str]:
    # Schema
    schema = select_schema(schema_sel)
    schema += await handler.augment_schema(init_queries=[
        get_properties, get_relationships
    ])

    # Prompt to process the user query
    query_prompt = select_prompt(prompt_sel, schema)

    # Prompt to process the query results
    ans_prompt = select_answer(ans_sel)

    return query_prompt, ans_prompt
