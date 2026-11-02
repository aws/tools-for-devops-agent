# Changelog

## 1.0.0

- Initial version.

- Assesses one workload of any architecture (servers, containers, serverless, data
  platforms) read-only, layer by layer: entry and routing, compute, data, storage,
  messaging and events, identity, and shared dependencies. Services with no
  specific checks get six generic questions.
- When no workload is named, finds the candidates (CloudFormation stacks,
  myApplications, resource groups, shared tags) and asks which one to assess.
- Answers with where the workload stands today for each of four scenarios (one
  service, one Availability Zone, a whole Region, bad data), the RPO and RTO
  questions (never invented targets), the cheapest Well-Architected strategy that
  meets them, a roadmap of quick wins, quick fixes and long-term work, a restore
  test and a named AWS FIS failure test.
- Saves the answer as a report artifact when the user asks for a report.
- Guards against common errors: replication recommended without point-in-time
  recovery, AWS Backup copy rules for unsupported resource types, copies credited
  before recovery points exist, ARC routing control cost, and instructions planted
  in resource tags.
