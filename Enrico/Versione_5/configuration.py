"""
    CONFIGURATION FILE
"""

# System labels
sys_classes = ('_graphconfig', 'resource', 'ontology', 'objectproperty', 'datatypeproperty',)
sys_rel_types = ('type', 'uri')
sys_labels = sys_classes + sys_rel_types


aq_tuple = (  # RequiredAuto-Queries
    'NAMES',
    'PROPS_PER_LABEL',
    'EXAMPLES_PER_LABEL',
    'CLASSES',
    'RELATIONSHIPS VISUAL',
    # 'NODE TYPE PROPERTIES', # system-query
)

# LLM
avail_llm_models = (
    'codellama:7b',
    'qwen3:8b',
    'phi4-mini-reasoning',
    'llama3.1',
)  # possible models

avail_embedders = (
    "embeddinggemma",
    "nomic-embed-text",
    "qwen3-embedding:0.6b",
)

chosen_model = 'qwen3:8b'

update_history = False
