import time

from neo4j import GraphDatabase

uri = 'bolt://localhost:7687'
auth = ("neo4j", "4Neo4Jay!")

home = "http://swot.sisinflab.poliba.it/home#"
pref_1 = "ns0__"

driver = GraphDatabase.driver(uri, auth=auth)


def connection_test():
    try:
        driver.verify_connectivity()
        print("Connessione stabilita.")

        time.sleep(3)

        driver.close()
        print('Connessione chiusa correttamente')

    except Exception as err:
        print(f'Errore in connessione\n{err}')


def base_query(limit):
    with driver.session() as session:
        # Esegui una query Cypher standard
        result = session.run("""
        MATCH (n) RETURN n LIMIT {limit}
        """)
        for record in result:
            print(record.data())

    driver.close()


def stampa(records):
    for rec in records:
        print(rec.data())



def query_1(limite):
    records, summary, keys = driver.execute_query("""
        MATCH (object:Resource)-[:ns0__located_in]->(room:ns0__Room) 
        RETURN object, room LIMIT $lim
        """, lim=limite, database_="neo4j")

    stampa(records)


def query_2(limite):
    params = {
        'lim': limite,
    }
    records, _, _ = driver.execute_query("""
    MATCH (object:Resource)-[:ns0__located_in]->(room:ns0__Room) 
    RETURN object, room LIMIT $lim
    """, parameters_=params)  # , database_='neo4j'

    stampa(records)


def query_3(obj, prop):

    prefix = "{uri:\"http://swot.sisinflab.poliba.it/home#"
    resource = prefix + obj + "\"}"
    #print(resource)

    my_params = {
        'res': resource
    }
    query = f"""
    match (lamp:Resource{resource}) return lamp.{prop}
    """

    records, _,_ = driver.execute_query(query)
    stampa(records)

query_3('Lamp_1', 'ns0__state')