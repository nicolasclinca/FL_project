# Note di Enrico

# Prova di Commit

# Cartelle

Cartella del repo:

```
~/Sync-PC/Formal Languages/Repo-FLeC
```

Cartella del server di Neo4j:

```
~/Programmi/neo4j-server/bin
```

Avviamento del server:

```
sudo ./neo4j console
```

# Spiegazione di Enrico

La cartella `Versione_1` contiene il progetto nella sua prima versione: l'unica differenza è che conto di sostituire `simple_init` e `complex_init` con `initialization` (al momento vuoto).

Il file `test` è fine a sè stesso, lo eliminerò

Il file `main_pipeline` contiene una spiegazione di tutte 

# Guida

- Importare un'ontologia

  ```cypher
  CREATE CONSTRAINT n10s_unique_uri FOR (r:Resource) REQUIRE r.uri IS UNIQUE;

  CALL n10s.rdf.import.fetch("https://raw.githubusercontent.com/nicolasclinca/FL_project/refs/heads/main/home.ttl", "Turtle");
  ```
  Nel prompt di sistema bisogna inserire lo schema del grafo dell'ontologia importata in neo4j.
- recuperare le etichette dei nodi (Classi/risorse)

  ```
  CALL db.labels() YIELD label RETURN label;
  ```
- Recuperare i Tipi di Relazione (Proprietà Ontologiche)

  ```cypher
  CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType;
  ```
- Recuperare le Proprietà dei Nodi e delle Relazioni:
  Le proprietà sui nodi e sulle relazioni contengono gli attributi specifici
  degli individui o delle relazioni.

  (proprietà dei nodi)

  ```
  MATCH (n)
  UNWIND keys(n) AS propertyKey
  RETURN DISTINCT propertyKey
  ```
  (proprietà delle relazioni)

  ```
  MATCH ()-[r]->()
  UNWIND keys(r) AS propertyKey
  RETURN DISTINCT propertyKey;
  ```
- Recuperare un Campione di Individui (Istanze)

  - Per dare all'LLM un'idea dei dati reali, puoi recuperare un piccolo campione di nodi per ogni etichetta e alcune delle loro proprietà.

    ```
    MATCH (n:Persona)
    RETURN n LIMIT 5;
    ```
    Questa query recupera 5 nodi con l'etichetta Persona e tutte le loro proprietà.
    Puoi ripeterlo per le etichette più importanti.
- Recuperare la Struttura Completa di Nodi e Relazioni (per una rappresentazione più dettagliata)
  Per fornire all'LLM un'idea di come nodi e relazioni sono collegati e quali proprietà possiedono,
  puoi estrarre la struttura.

  ```
  MATCH (n)-[r]->(m)
  RETURN DISTINCT labels(n) AS fromNodeLabels, type(r) AS relationshipType, labels(m) AS toNodeLabels
  LIMIT 100 // Limita il numero di risultati se il grafo è molto denso
  ```
  Questa query mostra quali tipi di nodi sono connessi da quali tipi di relazioni.
  È molto utile per costruire un modello mentale del grafo.
- Informazioni Specifiche da Neosemantics (se utili)
  Neosemantics aggiunge alcune proprietà e relazioni speciali che potresti voler includere nello schema
  se pensi che possano aiutare l'LLM a capire la provenienza dei dati o a costruire query più avanzate.
- Proprietà uri: Ogni nodo importato da un'ontologia avrà una proprietà uri che rappresenta l'URI RDF
  dell'individuo o della classe.
- Relazioni `ns:a (o rdf:type): Neosemantics` usa spesso `ns:a (o rdf:type)`
  per indicare l'appartenenza a una classe. Potresti voler menzionare che i nodi con l'etichetta Thing e
  una relazione ns:a verso un altro nodo rappresentano istanze di quella classe.
- Relazioni `rdfs:subClassOf, owl:sameAs, ecc.`

  - Se la tua ontologia contiene assiomi come `rdfs:subClassOf`,
    questi saranno modellati come relazioni esplicite nel grafo.
  - Esempio per trovare nodi con uri:

    ```
    MATCH (n) WHERE EXISTS(n.uri) RETURN DISTINCT labels(n), n.uri LIMIT 5
    ```
