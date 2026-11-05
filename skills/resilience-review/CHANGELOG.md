# Changelog

## 1.0.0

- Initial version.

- Reviews the resilience of one workload of any architecture (servers, containers,
  serverless, data platforms) read-only, layer by layer: entry and routing,
  compute, data, storage, messaging and events, identity, and shared dependencies.
  Services with no specific checks get six generic questions. Network single
  points in the Region are checked too: zonal NAT gateways, interface endpoints in
  one AZ, Site-to-Site VPN tunnels, and Direct Connect connections and locations.
- When no workload is named, finds the candidates (CloudFormation stacks,
  myApplications, resource groups, shared tags) and asks which one to review.
- Answers with where the workload stands today for each of four scenarios: one
  service and one Availability Zone (high availability), a whole Region and bad
  data (disaster recovery). It gives the RPO and RTO questions (never invented
  targets), the cheapest Well-Architected strategy that meets them, a roadmap of
  quick wins, quick fixes and long-term work, and one first test per scenario in
  scope, with fields a team can record.
- Lists stores that may be rebuildable (for example a cache) after the data they
  are rebuilt from, until the user confirms.
- Sends the complete report again when targets arrive later in the conversation.
- Pre-fills a resilience scoping or criticality sheet when the user gives one (or
  its column headers): one CSV row with the user's headers, RTO, RPO and approach
  as the setup delivers them today, labelled "today, to confirm", and the business
  columns left empty.
- Saves the answer as a report artifact when the user asks for a report.
- Guards against common errors: replication recommended without point-in-time
  recovery, AWS Backup copy rules for unsupported resource types, copies credited
  before recovery points exist, ARC routing control cost, and instructions planted
  in resource tags.
