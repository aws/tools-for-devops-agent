# Vector store checks

Findings are scoped by vector store type so they don't fire falsely. Determine the store type
from `GetKnowledgeBase` before running any of these.

## OpenSearch Serverless (AOSS)

Reads: `aoss:BatchGetCollection`, `GetSecurityPolicy`/`ListSecurityPolicies`,
`GetAccessPolicy`/`ListAccessPolicies`, `ListVpcEndpoints`.

- **Collection state:** must be `ACTIVE` (`BatchGetCollection`). Not active -> HIGH.
- **Network policy:** a private collection needs `SourceServices: ["bedrock.amazonaws.com"]`
  or a VPC endpoint in its network policy. `AllowFromPublic: true` overrides both. Private
  with neither -> HIGH.
- **Data access policy:** must grant the knowledge base service role. Missing the role -> HIGH.
- **Index engine (`faiss` vs `nmslib`):** NOT visible from the control plane -> **Inspect**,
  give the operator the data-plane check. Never pass/fail.

Refs: AOSS network policies; KB data-source sync prerequisites.

## Aurora (PostgreSQL / pgvector)

Reads: `rds:DescribeDBClusters`, `secretsmanager:DescribeSecret` (existence only, never the
value), `kms:DescribeKey`.

- **Cluster available** (`DescribeDBClusters`). Not available -> HIGH.
- **RDS Data API enabled** (`HttpEndpointEnabled` in `DescribeDBClusters`). Off -> HIGH.
- **Credentials secret exists** (`DescribeSecret`). Missing -> HIGH. Never read the value.
- **Table columns / schema:** NOT visible from the control plane -> **Inspect**, give the SQL
  check for the operator. Never pass/fail.

Ref: Aurora PostgreSQL as a Bedrock KB vector store.

## Third-party and S3 Vectors stores (disclose, do not check)

- **Pinecone, Redis Enterprise Cloud, MongoDB Atlas:** not checkable from AWS APIs -> report
  **Not checked** with the reason.
- **S3 Vectors stores:** `s3vectors:*` reads are not in `AIDevOpsAgentAccessPolicy` -> report
  **Not checked**.

## Deferred store types (v1 does not cover)

Kendra GenAI index, structured (Redshift), and graph (Neptune Analytics) knowledge bases have
different ingestion models and log-delivery support -> defer to a later version; name them,
do not attempt.
