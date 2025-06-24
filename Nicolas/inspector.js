import { toGraphQLTypeDefs } from "@neo4j/introspector";
import { driver as _driver, auth, session } from "neo4j-driver";
import { writeFileSync } from "fs";

const driver = _driver("neo4j://localhost:7687", auth.basic("neo4j", "Passworddineo4j1!"));

const sessionFactory = () => driver.session({ defaultAccessMode: session.READ });

// We create a async function here until "top level await" has landed
// so we can use async/await
async function main() {
    const typeDefs = await toGraphQLTypeDefs(sessionFactory);
    writeFileSync("schema.graphql", typeDefs);
    await driver.close();
}
main();