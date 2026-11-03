# Customer-Owned IP Tracing

Use this procedure when customer-owned public IPs (including BYOIP) are a significant NAT Gateway traffic category.

## Procedure

1. **ASN lookup (customer runs this)** — the agent has no shell, so it cannot run DNS lookups itself. Run Step 2 first: an IP that `describe-addresses` finds belongs to this account and needs no ASN lookup. For a destination IP not found in the account, give the customer this command to run to confirm whether the IP is hosted in AWS:
   ```
   dig TXT <reversed-ip>.origin.asn.cymru.com
   ```
   ASN **AS16509** or **AS14618** means the IP is AWS-hosted (this covers BYOIP ranges announced through AWS). Until the customer reports the result, state that the IP's ownership is unconfirmed.

2. **EIP trace** — if the IP is a customer Elastic IP:
   ```
   describe-addresses --filters Name=public-ip,Values=<public-ip>
   ```
   Check the `serviceManaged` field — a value like `rds` means the EIP is managed by (and belongs to) an AWS-managed service, not a customer-controlled resource.

3. **ENI → VPC mapping** — resolve the network interface behind the IP:
   ```
   describe-network-interfaces --network-interface-ids <eni-from-eip>
   ```

4. **Destination VPC CIDR**:
   ```
   describe-vpcs --vpc-ids <destination-vpc-id>
   ```

5. **Peering check** — for both the source VPC and the destination VPC:
   ```
   describe-vpc-peering-connections
   ```

6. **Route table verification** — if a peering connection exists, confirm the peering route is present in **every** route table associated with the subnets generating this traffic, not just one. A peering connection existing does not mean it's usable from every subnet — see Hard Rule 8 in SKILL.md.

7. **Interface Endpoint check** — for AWS-managed-service destinations (e.g., RDS):
   ```
   describe-vpc-endpoints --filters Name=vpc-endpoint-type,Values=Interface
   ```

## Root-cause determination

| Condition | Likely root cause | Fix |
|---|---|---|
| Peering exists + routes exist everywhere needed | Application is using the public IP directly (DNS/config issue), or a specific subnet's route table is missing the route despite others having it | Point application to the private IP / private endpoint; or add the missing route to the specific route table |
| Peering exists + routes missing in some route tables | Incomplete peering rollout | Add the peering route to every route table associated with subnets generating this traffic |
| No peering connection | No private path exists yet | Create VPC Peering (after checking for CIDR overlap) or use PrivateLink |
| EIP shows `serviceManaged: rds` | Traffic is going to an RDS instance's public endpoint | Investigate private connectivity for RDS (see below) |

## RDS instance identification (via `describeNetworkInterfaces`)

When the ENI lookup in step 3 returns description = `RDSNetworkInterface`, this **confirms** the destination is an RDS instance, but has real limits.

**What the lookup confirms:**
- Public IP, private IP, VPC ID, Availability Zone, and security group names — all directly usable and verified.
- That it *is* an RDS instance, not an EC2 instance.

**What the lookup does NOT provide — and cannot be worked around from the AWS side:**
- The RDS instance identifier (e.g., `prod-report-db-1`).
- `describeDBInstances` does not expose private IP as a filterable field, so you cannot reverse-lookup the instance name from the IP via that API.
- VPC-ID filters are also not supported on `describeDBInstances`, and in some cases the VPC ID reported by the ENI differs from what `describeDBInstances` reports for the same instance (an artifact of RDS's internal networking) — so even a VPC-ID-based cross-reference can be unreliable.

**What to hand back to the customer instead of the instance name:**
- The verified public IP, private IP, VPC, AZ, and security group names.
- A note that they can self-match to an instance name by filtering the RDS console by VPC, or by resolving the RDS endpoint hostname via `nslookup` from inside the VPC.

## IP stability — a caveat for customers acting on these findings later

- **Aurora:** IPs are stable. Aurora clusters cannot be stopped, so the ENI and its IP persist indefinitely — a finding based on an Aurora IP remains valid.
- **Non-Aurora RDS:** IPs can change on a stop/start cycle. If the instance was restarted after the flow log capture window, a finding based on its IP may be stale — note this explicitly when the engine isn't Aurora.
