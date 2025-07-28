"""
Schemas and base prompts for queries and answers
"""


class ExamplePrompts:
    example_test = """
    """

    example_1 = """
    EXAMPLES
    
    "Which movies Tom Hanks acted in?" 
    MATCH (th:Actor{name:'TomHanks'})-[:ACTED_IN]->(m:Movie) RETURN m.name AS title
    
    "Which Nation Rome is in?"
    MATCH (c:City{name:'Rome'})-[:IS_IN]->(n:Nation) RETURN n.name as nation
    
    """


class QuestionPrompts:

    instruction_test = f"""
    Generate the Cypher query that best answers the user query.
    Follow these guidelines:

    1. Always output a syntactically correct Cypher query. 
    2. Use only the node labels, relationship types, and property keys provided in the schema.
    3. Use specific names only if explicitly mentioned in the question.
    4. Do not invent properties or overly specific details.
    5. Keep queries syntactically correct, simple, and readable.
    6. Access node properties using dot notation (e.g., `n.name`).
    
    """

    instruction_pmt_1 = """
    You are an expert Cypher generator: your task is to answer questions about a knowledge graph database. 
    You have to query a Neo4j server using a Cypher query. 
    Be sure it's a valid Cypher query: the server should be able to execute it. 
    Write only the query. 
    
    Here's some examples of correct queries
    """


class AnswerPrompts:
    answer_prompt = """
    You are a helpful smart assistant.
    You'll receive the results of the query, written in Cypher language: try to explain these results in natural language. 
    Please, be concised and synthetic. 
    """


EP = ExamplePrompts
AP = AnswerPrompts
QP = QuestionPrompts

if __name__ == "__main__":
    pass
