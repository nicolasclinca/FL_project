from neo4j import GraphDatabase

# import ast

uri = 'bolt://localhost:7687'
auth = ("neo4j", "4Neo4Jay!")
home = "http://swot.sisinflab.poliba.it/home#"
driver = GraphDatabase.driver(uri, auth=auth)


def print_records(result, var="n"):
    for record in result:
        print(record.data())


def all_nodes_query(tx):
    result = tx.run("MATCH (n) RETURN n LIMIT 10")
    print_records(result)


def print_classes(tx):
    result = tx.run("""
    MATCH (n:owl__Class) 
    RETURN DISTINCT replace(toString(n.uri), "http://swot.sisinflab.poliba.it/home#", "home:") AS class
    ORDER BY class;
    """)
    print_records(result, "class")


def devices_query(tx):
    result = tx.run("""
        MATCH (n:owl__Class) 
        WHERE NOT(n.uri STARTS WITH "bnode:")
        RETURN DISTINCT replace(toString(n.uri), "http://swot.sisinflab.poliba.it/home#", "") AS class
        ORDER BY class;
        """)
    text = ""
    sep = "\n"
    for record in result:
        text = text + str(record['class']) + sep
    return text


def devices_map(tx):
    result = tx.run("""
    MATCH (res:Resource)-[:ns0__located_in]->(room:ns0__Room) 
    RETURN DISTINCT replace(toString(res.uri), "http://swot.sisinflab.poliba.it/home#", "") AS obj, 
    replace(toString(room.uri), "http://swot.sisinflab.poliba.it/home#", "") AS room; 
    """)
    text = "Devices' allocations in Rooms:\n"
    sep = "\n"
    for record in result:
        text = text + f"{record['obj']} is in {record['room']}" + sep
    return text


def main_execute(function):
    with driver.session() as session:
        print(session.execute_read(function))


main_execute(devices_map)  # inserire il nome della funzione senza le parentesi tonde né il tx
