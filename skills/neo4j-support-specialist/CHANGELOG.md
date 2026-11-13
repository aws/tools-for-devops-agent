# Changelog

## 1.0.0

- Initial version. SKILL.md sets the rules, evidence order and report format and indexes runbooks A1 to A12, which
  cover 77 common operational issues. References cover evidence sources, log queries, operator commands and a map from 3.x, 4.x and 5.x names to 2026.x
- Error texts, log formats, defaults and commands checked against Neo4j 2026.10.1 on EKS, ECS and EC2
- Community Edition: edition detection, what Community lacks, and the signatures that differ from Enterprise
- Optional live database checks through the Neo4j connector's `read-cypher` tool, limited to the read-only queries in
  `references/live-database.md`
