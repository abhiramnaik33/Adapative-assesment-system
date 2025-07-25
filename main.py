from neo4j import GraphDatabase

uri = "bolt://localhost:7687"
driver = GraphDatabase.driver(uri, auth=("neo4j", "24681379"))

try:
    with driver.session() as session:
        result = session.run("RETURN 1")
        print("Connection successful:", result.single()[0])
except Exception as e:
    print("Connection failed:", e)
finally:
    driver.close()
