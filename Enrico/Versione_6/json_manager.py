import json

INPUT_FILE = '../../queries.json'
OUTPUT_FILE = './query_base.json'


def json_converter(input_file: str, out_file: str):
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError(f"Error: {input_file} is not a list")

        for i, item in enumerate(data):
            item['ID'] = i + 1

        if out_file[-1] == 'n':  # JSON output
            with open(out_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

        elif out_file[-1] == 'l':  # JSONL output
            with open(out_file, 'w', encoding='utf-8') as f:
                for item in data:
                    f.write(json.dumps(item, ensure_ascii=False) + '\n')

        print(f"Saved in {out_file}")

    except FileNotFoundError:
        print(f"Errore: Il file '{input_file}' non è stato trovato.")
    except Exception as e:
        print(f"Si è verificato un errore: {e}")


if __name__ == '__main__':
    json_converter(INPUT_FILE, OUTPUT_FILE)
