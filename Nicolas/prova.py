from neo4j import GraphDatabase
from collections import defaultdict

# 👉 Configura i dati di connessione qui
NEO4J_URI = "bolt://localhost:7687"
USERNAME = "neo4j"
PASSWORD = "Passworddineo4j1!"

class GraphSchemaExtractor:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def extract_schema(self):
        with self.driver.session() as session:
            labels = session.run("CALL db.labels()").value()
            rel_types = session.run("CALL db.relationshipTypes()").value()

            node_props = defaultdict(set)
            rel_props = defaultdict(set)
            rel_directions = defaultdict(set)

            for label in labels:
                query = f"""
                MATCH (n:`{label}`) 
                WITH n LIMIT 100 
                UNWIND keys(n) AS key 
                RETURN DISTINCT key
                """
                result = session.run(query)
                for record in result:
                    node_props[label].add(record["key"])

            for rel_type in rel_types:
                query = f"""
                MATCH (a)-[r:`{rel_type}`]->(b) 
                WITH r LIMIT 100 
                UNWIND keys(r) AS key 
                RETURN DISTINCT key
                """
                result = session.run(query)
                for record in result:
                    rel_props[rel_type].add(record["key"])

                # Tipi di nodi collegati
                query_types = f"""
                MATCH (a)-[r:`{rel_type}`]->(b) 
                RETURN DISTINCT labels(a) AS from_labels, labels(b) AS to_labels 
                LIMIT 100
                """
                result = session.run(query_types)
                for record in result:
                    from_labels = ":".join(record["from_labels"])
                    to_labels = ":".join(record["to_labels"])
                    rel_directions[rel_type].add((from_labels, to_labels))

            # Stampa schema leggibile
            print("\n=== NODE TYPES ===")
            for label in labels:
                props = ", ".join(sorted(node_props[label])) or "no properties"
                print(f"- {label} ({props})")

            print("\n=== RELATIONSHIP TYPES ===")
            for rel_type in rel_types:
                props = ", ".join(sorted(rel_props[rel_type])) or "no properties"
                directions = rel_directions[rel_type]
                for from_label, to_label in directions:
                    print(f"- ({from_label})-[:{rel_type} {{{props}}}]->({to_label})")

if __name__ == "__main__":
    extractor = GraphSchemaExtractor(NEO4J_URI, USERNAME, PASSWORD)
    extractor.extract_schema()
    extractor.close()
