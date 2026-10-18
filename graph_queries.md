# FalkorDB Browser queries

Open `http://localhost:3001`, then select the `signalshield` graph. Paste one query at a time.

## 1. Official-evidence paths

```cypher
MATCH path = (claim:Claim)-[:MENTIONS]->(company:Company)-[:PUBLISHED]->(filing:Disclosure)-[:SOURCED_FROM]->(source:Source)
RETURN path
LIMIT 30
```

## 2. Agent coordination after creating a case

```cypher
MATCH path = (from:Agent)-[:HANDOFF_TO]->(:AgentHandoff)-[:CREATED]->(:ReviewCase)-[:REVIEWS]->(:Claim)
RETURN path
```

## 3. Persistent human memory after saving a decision

```cypher
MATCH path = (:ReviewCase)-[:RESOLVED_WITH]->(decision:Decision)-[:ABOUT]->(:Claim)
RETURN path
```

## 4. Small, presentation-friendly overview

```cypher
MATCH path = (claim:Claim {id: 'claim-demo-001'})-[:MENTIONS]->(:Company)-[:PUBLISHED]->(:Disclosure)-[:SOURCED_FROM]->(:Source)
RETURN path
LIMIT 8
```

## 5. Claim-to-portfolio exposure

```cypher
MATCH path = (:Claim {id: 'claim-demo-001'})-[:MENTIONS]->(:Company)<-[:IN_COMPANY]-(:Position)<-[:HOLDS]-(:Portfolio)
RETURN path
```
