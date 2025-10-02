"""
    CONFIGURATION FILE
"""

# System labels
sys_classes = ('_graphconfig', 'resource', 'ontology', 'objectproperty', 'datatypeproperty',)
sys_rel_types = ('type', 'uri')
sys_labels = sys_classes + sys_rel_types


aq_tuple = (  # RequiredAuto-Queries
    # 'LABELS',
    # 'PROPERTIES',
    # 'RELATIONSHIP TYPES',
    # 'RELATIONSHIPS LIST',
    'NAMES',
    # 'NODES_WITH_PROPS',
    # 'GLOBAL SCHEMA',
    'PROPS_PER_LABEL',
    'EXAMPLES_PER_LABEL',
    'CLASSES',
    'RELATIONSHIPS VISUAL',
    # 'NODE PROPERTIES',
)

# LLM
installed_models = ('codellama:7b',
                    'qwen3:8b',
                    'phi4-mini-reasoning',
                    'llama3.1',)  # possible models
chosen_model = 'qwen3:4b'

update_history = False
