"""
Schemas and base prompts for queries and answers
"""


class ExampleLists:
    specific_examples = [
        # {
        #     "user_query": "Check the oven temperature setting.", # ID: 2
        #     "cypher_query": "MATCH (n:NamedIndividual {name: 'Oven'}) return n.setting"
        # },
        {
            "user_query": "Is the coffee machine on?", # ID 1
            "cypher_query": "MATCH (cm:NamedIndividual {name: 'Coffee_machine_1'}) WHERE cm.state = ['on'] RETURN count(cm) > 0 AS is_on"
        },
        {
            "user_query": "Check the temperature setting of air conditioners.", # ID 44
            "cypher_query": "MATCH (ac:NamedIndividual)-[:MEMBEROF]->(c:Class {name:'Air_conditioner'}) RETURN ac.setting"
        },
        # {
        #     "user_query": "What devices are currently on in the bedroom?", # ID 20
        #     "cypher_query": "MATCH (d:NamedIndividual)-[:LOCATED_IN]->(r:Room {name: 'Bedroom'}) WHERE d.state="
        #                     "['on'] RETURN d.name"
        # },
        {
            "user_query": "List all rooms with active occupancy sensors.",  # ID:41
            "cypher_query": "MATCH (r:Room)-[:CONTAINS]->(os:NamedIndividual {value:[true]})-[:MEMBEROF]->(:Class{name:'Occupancy_sensor'}) RETURN r.name "
        },
        {
            "user_query": "Which rooms contain dimmable lights?", # ID: 29
            "cypher_query": "MATCH (r:Room)-[:CONTAINS]->(dl:NamedIndividual), (dl:NamedIndividual)-[:MEMBEROF]->(cls:Class{name:'Dimmable_light'}) RETURN r"
        },
        {
            "user_query": "List all appliances in the bathroom", # Inventata
            "cypher_query": "MATCH (b:Room{name:'Bathroom'})-[:CONTAINS]->(n:NamedIndividual)-[:MEMBEROF]->(a:Class {name:'Appliance'}) RETURN n.name "
        },
    ]

    example_list = [
        {
            "user_query": "Which people live in Paris?",
            "cypher_query": "MATCH (p:Person)-[:LIVES_IN]->(c:City {name: 'Paris'}) RETURN p.name"
        },
        {
            "user_query": "Which books were published after the year 2000?",
            "cypher_query": "MATCH (b:Book) WHERE b.year > 2000 RETURN b.title"
        },
        # {
        #     "user_query": "Who are the friends of John?",
        #     "cypher_query": "MATCH (p:Person {name: 'John'})-[:FRIEND_OF]-(f:Person) RETURN f.name"
        # },
        # {
        #     "user_query": "Which utilities are related to something containing the word climate?",
        #     "cypher_query": "MATCH (r:Resource)-[:RELATED_TO]->(t:Topic) WHERE t.uri CONTAINS 'climate' RETURN r"
        # },
        # {
        #     "user_query": "Which employees work for companies based in Germany?",
        #     "cypher_query":
        #         "MATCH (e:Person)-[:WORKS_AT]->(c:Company)-[:BASED_IN]->(:Country {name: 'Germany'}) RETURN e.name"
        # },
        {
            "user_query": "Is there any user with age 38?",
            "cypher_query":
                "MATCH (u:User) WHERE u.age = 38 RETURN COUNT(u) > 0 AS user_exists",
        },
        # {
        #     "user_query": "Is there an order with a value greater than 100?",
        #     "cypher_query":
        #     "MATCH (o:Order) WITH collect(o) AS orders
        #     RETURN ANY(order IN orders WHERE order.value > 100) AS is_great"
        # }
    ]


class QuestionPrompts:
    instructions_prompt = """
You are an expert Cypher generator: your task is to generate Cypher query that best answers the user question.

Follow these guidelines:
    1. Write ONLY a syntactically correct Cypher query: nothing else. 
    2. DO NOT invent properties, relationships or objects: read the database schema.   
    3. Keep the queries simple, readable and deterministic. 
    
    """

    instructions_prompt_1 = """
You are an expert Cypher generator: your task is to generate Cypher query that best answers the user question.
    
Follow these guidelines:
    1. Always output a syntactically correct Cypher query and nothing else. 
    2. Use only the node labels, relationship types, and property keys provided in the schema.
    3. Use specific names only if explicitly mentioned in the question.
    4. Do not invent properties or overly specific details.
    5. Keep queries syntactically correct, simple, and readable.
    6. Access node properties using dot notation (e.g., `n.name`).
    
    """


class AnswerPrompts:
    answer_prompt = """
You are a helpful smart assistant.
You'll receive the outputs of the query, written in Cypher language: explain these outputs in a natural way.
Please, be synthetic: read the outputs and explain them by answering to the user question.  
    """


EL = ExampleLists
AP = AnswerPrompts
QP = QuestionPrompts

if __name__ == "__main__":
    pass
