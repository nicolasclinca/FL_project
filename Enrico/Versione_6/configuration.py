"""
    CONFIGURATION FILE
"""
from collections import defaultdict
from resources.prompts import QP, AP

config = defaultdict()

# NEO4J
config['n4j_usr'] = 'neo4j'  # Neo4j Username
config['n4j_psw'] = '4Neo4Jay!'  # Neo4j Password
config['n4j_url'] = 'bolt://localhost:7687'  # Neo4j URI/URL

# System labels
sys_classes = ('_graphconfig', 'resource', 'ontology', 'objectproperty', 'datatypeproperty',)
sys_rel_types = ('type', 'uri')
sys_labels = sys_classes + sys_rel_types

# AUTO-QUERIES

aq_tuple = (  # RequiredAuto-Queries
    ('NAMES', 'init',),
    ('PROPS_PER_LABEL', 'init',),
    ('OBJECT PROPERTIES', 'filter',),
    ('RELATIONSHIPS VISUAL', 'init',0,),
    ('CLASS HIERARCHY', 'init',),
)
config['aq_tuple'] = aq_tuple

# LANGUAGE MODEL
config['llm'] = 'llama3.1:latest'
config['upd_hist'] = False  # Update the history, by adding chat results
config['quit_key_words'] = (
    "#", "§",
    "bye", "bye bye", "close",
    "esc", "exit", "goodbye", "quit",
)  # Keywords to quit the chat

# EMBEDDING MODEL
config['embd'] = "nomic-embed-text:latest"  # Embedding Model

# RETRIEVER
config['filtering'] = True  # Indicate if the schema should be filtrated
config['k_lim'] = 5  # Maximum number of examples to be extracted

# PROMPTS
config['question_prompt'] = QP.instructions_prompt
config['answer_prompt'] = AP.answer_prompt

if __name__ == "__main__":
    print(list(config['AQ_dict'].items()))
