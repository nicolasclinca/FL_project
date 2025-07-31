"""
Schemas and base prompts for queries and answers
"""


class ExampleLists:

    example_list_1 = [
        {
            "user_query": "Which movies Tom Hanks acted in?",
            "cypher_query": "MATCH (th:Actor{name:'TomHanks'})-[:ACTED_IN]->(m:Movie) RETURN m.name AS title"
        },
        {
            "user_query": "Which Nation Rome is in?",
            "cypher_query": "MATCH (c:City{name:'Rome'})-[:IS_IN]->(n:Nation) RETURN n.name as nation"
        },
    ]

    testing_examples = [
        {
            "user_query": "Which people live in Paris?",
            "cypher_query": "MATCH (p:Person)-[:LIVES_IN]->(c:City {name: 'Paris'}) RETURN p.name"
        },
        {
            "user_query": "Which books were published after the year 2000?",
            "cypher_query": "MATCH (b:Book) WHERE b.year > 2000 RETURN b.title"
        },
        {
            "user_query": "Who are the friends of John?",
            "cypher_query": "MATCH (p:Person {name: 'John'})-[:FRIEND_OF]-(f:Person) RETURN f.name"
        },
        {
            "user_query": "Which resources are related to something containing the word climate?",
            "cypher_query": "MATCH (r:Resource)-[:RELATED_TO]->(t:Topic) WHERE t.uri CONTAINS 'climate' RETURN r"
        },
        {
            "user_query": "Which employees work for companies based in Germany?",
            "cypher_query":
                "MATCH (e:Person)-[:WORKS_AT]->(c:Company)-[:BASED_IN]->(:Country {name: 'Germany'}) RETURN e.name"
        },
    ]


class QuestionPrompts:

    instruction_pmt_1 = """
    You are an expert Cypher generator: your task is to answer questions about a knowledge graph database. 
    You have to query a Neo4j server using a Cypher query. 
    Be sure it's a valid Cypher query: the server should be able to execute it. 
    Write only the query. 
    
    Here's some examples of correct queries
    """

    testing_instructions = f"""
    Generate the Cypher query that best answers the user query.
    Follow these guidelines:

    1. Always output a syntactically correct Cypher query. 
    2. Use only the node labels, relationship types, and property keys provided in the schema.
    3. Use specific names only if explicitly mentioned in the question.
    4. Do not invent properties or overly specific details.
    5. Keep queries syntactically correct, simple, and readable.
    6. Access node properties using dot notation (e.g., `n.name`).
    
    """


class AnswerPrompts:
    answer_pmt_1 = """
    You are a helpful smart assistant.
    You'll receive the results of the query, written in Cypher language: try to explain these results in natural language. 
    Please, be concise and synthetic. 
    """

    testing_ans_pmt = answer_pmt_1


EL = ExampleLists
AP = AnswerPrompts
QP = QuestionPrompts

if __name__ == "__main__":
    pass
