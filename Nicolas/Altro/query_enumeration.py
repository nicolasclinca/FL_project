import json

# Caricamento del file JSON originale
with open('queries.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Apertura del file JSONL in scrittura
with open('labeled_data.jsonl', 'w', encoding='utf-8') as f:
    for idx, item in enumerate(data):
        record = {
            "query": item["query"],
            "output": item["output"],
            "label": None,  # Puoi cambiare in 0 o 1 a seconda del tuo criterio
            "description": None
        }
        f.write(json.dumps(record, ensure_ascii=False) + '\n')
        
        
        
