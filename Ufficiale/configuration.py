"""
    CONFIGURATION FILE
"""

from collections import defaultdict
from inputs.prompts import QP, AP, EL

config = defaultdict()

# NEO4J
config['n4j_usr'] = 'neo4j'  # Neo4j Username
config['n4j_psw'] = 'Passworddineo4j1!' # '4Neo4Jay!' # 'Passworddineo4j1!'
config['n4j_url'] = 'bolt://localhost:7687'  # Neo4j URI/URL

# System labels
sys_classes = ('_graphconfig', 'resource', 'ontology', 'objectproperty', 'datatypeproperty',)
sys_rel_types = ('type', 'uri')
sys_labels = sys_classes + sys_rel_types

# AUTO-QUERIES
aq_tuple = (  # RequiredAuto-Queries
    ('NAMES', 'init'),
    ('LABELS', 'init'),
    ('OBJECT PROPERTIES', 'filter', None, 3),
    # ('OBJECT CLASSES', 'filter', None, 2), # FIXME
    # ('PROPS_PER_LABEL', 'init'), # FIXME
    # ('CLASS HIERARCHY', 'init'), # FIXME
    ('RELATIONSHIPS VISUAL', 'init', 0),
    # ('RELATIONSHIPS NAMES', 'init'),

)
config['aq_tuple'] = aq_tuple

# LANGUAGE MODEL
config['llm'] = 'llama3.1:latest'  # 'llama3.1:latest' # 'qwen3:4b'
# config['upd_hist'] = False  # Update the history, by adding chat outputs
config['quit_key_words'] = (
    "#", "§",
    "bye", "bye bye", "close",
    "esc", "exit", "goodbye", "quit",
)  # Keywords to quit the chat

# EMBEDDING MODEL
config['embd'] = "nomic-embed-text:latest"  # Embedding Model

# RETRIEVER
config['filtering'] = True  # Indicate if the schema should be filtrated
config['k_lim'] = 3  # Maximum number of examples to be extracted
config['thresh'] = 0.5

# PROMPTS
config['question_prompt'] = QP.instructions_prompt
config['answer_prompt'] = AP.answer_prompt
config['examples'] = EL.generic_examples

if __name__ == "__main__":
    print(list(config['AQ_dict'].items()))
