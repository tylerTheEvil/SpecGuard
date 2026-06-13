// =========================================================
// SpecGuard Demo Queries — to be run after specguard_graph.cypher
// =========================================================
//
// These queries demonstrate the ANALYTICAL VALUE of representing
// requirements as a graph, beyond what single-requirement smell
// detection can achieve.
//
// Run each query separately in Neo4j Browser and observe results.
// =========================================================


// ---------------------------------------------------------
// Q1. Visualize the entire graph
// ---------------------------------------------------------
// Recommended: limit to 100 nodes so the canvas stays readable
MATCH (n) RETURN n LIMIT 100;


// ---------------------------------------------------------
// Q2. Show all requirements that mention the L1 write-through cache
// ---------------------------------------------------------
// This is impossible to do efficiently with text-based smell detector;
// a graph naturally answers this in one query.
MATCH (r:Requirement)-[:MENTIONS]->(c:Component {name: 'L1WTD'})
RETURN r.req_id AS id, r.text AS text, r.modal_strength AS strength
ORDER BY r.req_id;


// ---------------------------------------------------------
// Q3. Show requirements with smells, colored by smell type
// ---------------------------------------------------------
// In Neo4j Browser this gives a beautiful visualization of where
// quality issues cluster in the specification.
MATCH (r:Requirement)-[:HAS_SMELL]->(s:Smell)
RETURN r, s;


// ---------------------------------------------------------
// Q4. Group smells by severity and category
// ---------------------------------------------------------
// Aggregate analysis: which categories of requirements have the
// most quality issues? This drives prioritization for revision.
MATCH (r:Requirement)-[:HAS_SMELL]->(s:Smell)
RETURN
  r.category AS category,
  s.severity AS severity,
  count(*) AS count
ORDER BY category, severity DESC;


// ---------------------------------------------------------
// Q5. Find requirements with NO measurable criteria but mandatory modal
// ---------------------------------------------------------
// "shall" requirement without any external standard reference and
// without specific component is suspicious — too generic to verify.
MATCH (r:Requirement)
WHERE r.modal_strength = 'mandatory'
  AND NOT (r)-[:REFERS_TO]->(:Standard)
  AND NOT (r)-[:MENTIONS]->(:Component)
RETURN r.req_id AS id, r.text AS text;


// ---------------------------------------------------------
// Q6. Cross-cutting requirements (mention many components)
// ---------------------------------------------------------
// Requirements that touch multiple components are higher-risk
// for changes — impact analysis target.
MATCH (r:Requirement)-[:MENTIONS]->(c:Component)
WITH r, count(c) AS component_count, collect(c.name) AS components
WHERE component_count >= 2
RETURN r.req_id AS id, component_count, components, r.text AS text
ORDER BY component_count DESC;


// ---------------------------------------------------------
// Q7. Standards coverage — which external standards are referenced
// ---------------------------------------------------------
// Useful for regulatory / standards traceability matrix.
MATCH (r:Requirement)-[:REFERS_TO]->(s:Standard)
WITH s, count(r) AS reference_count, collect(r.req_id) AS referencing_reqs
RETURN s.name AS standard, s.description, reference_count, referencing_reqs
ORDER BY reference_count DESC;


// ---------------------------------------------------------
// Q8. Safety-critical requirements with quality issues
// ---------------------------------------------------------
// CRITICAL FINDING type — exactly the use case for the gate decision.
// Requirements marked safety-critical that have any smell are
// top-priority for revision.
MATCH (r:Requirement)-[:HAS_SMELL]->(s:Smell)
WHERE r.safety_critical = true
RETURN
  r.req_id AS id,
  r.text AS text,
  s.smell_type AS smell,
  s.severity AS severity,
  s.trigger AS trigger;


// ---------------------------------------------------------
// Q9. Component dependency graph for impact analysis
// ---------------------------------------------------------
// Given a component, what requirements would be affected by
// a change to it? Shows blast radius.
MATCH path = (r:Requirement)-[:MENTIONS]->(c:Component {name: 'L1WTD'})
RETURN path;


// ---------------------------------------------------------
// Q10. Configuration-specific requirement counts
// ---------------------------------------------------------
// How many requirements apply to each configuration variant?
MATCH (r:Requirement)-[:APPLIES_TO]->(cfg:Configuration)
WITH cfg, count(r) AS req_count, collect(r.req_id) AS reqs
RETURN cfg.name AS configuration, req_count, reqs;


// ---------------------------------------------------------
// Q11. Find requirements only with optional / recommended strength
// ---------------------------------------------------------
// "should" requirements are weaker — useful for negotiation
// or trimming when scope must be reduced.
MATCH (r:Requirement)
WHERE r.modal_strength = 'recommended'
RETURN r.req_id AS id, r.category AS category, r.text AS text
ORDER BY r.category, r.req_id;


// ---------------------------------------------------------
// Q12. Detect potential broken references — components mentioned
//      but not formally introduced by any "definition" requirement
// ---------------------------------------------------------
// Heuristic: every component should have at least one mandatory
// requirement that introduces it. If a component appears only in
// "should" requirements, the definition is weak.
MATCH (c:Component)<-[:MENTIONS]-(r:Requirement)
WITH c, collect(DISTINCT r.modal_strength) AS strengths
WHERE NOT 'mandatory' IN strengths
RETURN c.name AS component, c.full_name AS description, strengths;


// ---------------------------------------------------------
// Q13. Smells per component — quality heat map
// ---------------------------------------------------------
// Components whose requirements have the most smells indicate
// areas where the specification needs the most rework.
MATCH (c:Component)<-[:MENTIONS]-(r:Requirement)-[:HAS_SMELL]->(s:Smell)
WITH c, count(DISTINCT s) AS smell_count
RETURN c.name AS component, smell_count
ORDER BY smell_count DESC;


// ---------------------------------------------------------
// Q14. Find pairs of requirements that share components — possible
//      conflict candidates
// ---------------------------------------------------------
// Two requirements about the same component might contradict each
// other. This is candidate detection — humans review the pairs.
MATCH (r1:Requirement)-[:MENTIONS]->(c:Component)<-[:MENTIONS]-(r2:Requirement)
WHERE r1.req_id < r2.req_id
WITH r1, r2, count(c) AS shared_count, collect(c.name) AS shared_components
WHERE shared_count >= 2
RETURN
  r1.req_id AS req_a,
  r2.req_id AS req_b,
  shared_count,
  shared_components,
  r1.text AS text_a,
  r2.text AS text_b
ORDER BY shared_count DESC
LIMIT 15;


// ---------------------------------------------------------
// Q15. Requirement categorization summary
// ---------------------------------------------------------
// One-shot dashboard for the supervisor.
MATCH (r:Requirement)-[:BELONGS_TO]->(cat:Category)
WITH cat,
  count(r) AS total,
  sum(CASE r.safety_critical WHEN true THEN 1 ELSE 0 END) AS safety_critical,
  sum(CASE r.modal_strength WHEN 'mandatory' THEN 1 ELSE 0 END) AS mandatory,
  sum(CASE r.modal_strength WHEN 'recommended' THEN 1 ELSE 0 END) AS recommended
RETURN
  cat.name AS category,
  total,
  safety_critical,
  mandatory,
  recommended
ORDER BY total DESC;
