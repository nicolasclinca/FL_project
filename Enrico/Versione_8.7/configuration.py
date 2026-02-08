"""
    CONFIGURATION FILE
"""

from collections import defaultdict
from inputs.prompts import QP, AP, EL

config = defaultdict()

# NEO4J
config['n4j_usr'] = 'neo4j'  # Neo4j Username
config['n4j_psw'] = '4Neo4Jay!'  # 'Passworddineo4j1!' d'4Neo4Jay!'
# FIXME: la password va messa su None alla fine
config['n4j_url'] = 'bolt://localhost:7687'  # Neo4j URI/URL

# System labels
sys_classes = ('_graphconfig', 'resource', 'ontology', 'objectproperty', 'datatypeproperty',)
sys_rel_types = ('type', 'uri')
sys_labels = sys_classes + sys_rel_types

# AUTO-QUERIES


# LANGUAGE MODEL
config['llm'] = 'qwen3:4b'
"""
'llama3.1:latest'
'qwen3:4b'
'qwen3:8b'
"""

config['quit_key_words'] = (
    "#", "§",
    "bye", "bye bye", "close",
    "esc", "exit", "goodbye", "quit",
)  # Keywords to quit the chat

# EMBEDDING MODEL
config['embedder'] = 'nomic-embed-text-v2-moe:latest'
"""
'embeddinggemma:latest'
'nomic-embed-text-v2-moe:latest'
'qwen3-embedding:0.6b'
"""

# RETRIEVER
config['k_lim'] = 5  # Maximum number of examples to be extracted
config['thresh'] = 0.6  # Minimum similarity threshold for schema filtering

aq_tuple = (  # RequiredAuto-Queries, with name, phase and (maybe) parameters
    ('LABELS', 'dense-thresh'),
    ('NAMES', 'dense-klim'),
    ('OBJECT PROPERTIES', 'launch', None, 3, True),
    ('RELATIONSHIPS NAMES', 'dense-klim'),
)
config['aq_tuple'] = aq_tuple

# PROMPTS
config['question_prompt'] = QP.instructions_prompt
config['answer_prompt'] = AP.answer_prompt
config['examples'] = EL.generic_examples

# CHOOSE YOUR QUERIES
start = 57
config['test_queries'] = [
    # (33,35),
    (36,38)
]

if __name__ == "__main__":
    pass
