import json

# 1. Configurazione dei nomi file
input_file = 'original_queries.json'
output_json = 'Queries_with_ID.json'
# output_jsonl = 'Queries_with_ID.jsonl'

# 2. Caricamento del file JSON originale
try:
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Verifica che sia effettivamente una lista
    if not isinstance(data, list):
        raise ValueError("Il file JSON non contiene una lista.")

    # 3. Aggiunta dell'ID
    # Usiamo enumerate per ottenere sia l'indice (i) che l'oggetto (item)
    for i, item in enumerate(data):
        # Aggiungiamo la chiave 'ID' all'inizio o alla fine del dizionario
        # Nota: item['ID'] = i aggiunge la chiave.
        # Se vuoi che l'ID parta da 1 invece che da 0, usa: i + 1
        item['ID'] = i

        # --- OPZIONE A: Salvare come JSON classico (una lista di oggetti) ---
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"File JSON salvato come: {output_json}")

    # --- OPZIONE B: Salvare come JSONL (un oggetto per riga) ---
    with open(output_jsonl, 'w', encoding='utf-8') as f:
        for item in data:
            # dump di ogni singolo oggetto + nuova riga (\n)
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    print(f"File JSONL salvato come: {output_jsonl}")

except FileNotFoundError:
    print(f"Errore: Il file '{input_file}' non è stato trovato.")
except Exception as e:
    print(f"Si è verificato un errore: {e}")