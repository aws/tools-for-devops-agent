---
inclusion: manual
---

# AWS Networking Infrastructure Strategic Questions

Use these questions to guide discovery and architecture discussions for each AWS networking service. These ensure proper planning and successful implementation.

## Cloud WAN (CWAN)

### Network Architecture
1. How many AWS regions need to be connected?
2. What's your global network topology requirement?
3. How many VPCs and on-premises sites need connectivity?
4. Do you need network segmentation across your global network?
5. What's your branch office connectivity strategy?
6. How will you organize your network into segments?
7. What's your multi-account strategy?

### Security & Routing
1. What network segments require isolation?
2. How will you implement security policies across regions?
3. What's your routing policy strategy?
4. Do you need service insertion for traffic inspection?
5. How will you control inter-segment communication?
6. What's your attachment acceptance strategy?
7. What route filtering is required?

### Performance & Scale
1. What's your expected bandwidth per region?
2. How many attachments do you anticipate globally?
3. What are your latency requirements between regions?
4. Do you need optimized routing for performance?
5. What's your expected growth over 3-5 years?
6. How will you handle traffic prioritization?
7. What's your packet per second requirement?

### Cost Management
1. How will you optimize core network edge costs?
2. What's your expected data transfer volume?
3. Do you need multiple core networks for cost allocation?
4. How will you track usage per business unit or region?
5. What's your attachment strategy to minimize costs?
6. How will you balance cost vs. performance?
7. What's your budget for global connectivity?

### Operational
1. Who will manage Cloud WAN configurations?
2. What's your network monitoring strategy?
3. How will you handle policy changes?
4. What's your change management process?
5. How will you troubleshoot cross-region issues?
6. What automation is needed for network provisioning?
7. How will you manage network policies as code?

### Integration
1. Do you need SD-WAN integration?
2. What third-party network devices require connectivity?
3. How will you integrate with existing Transit Gateways?
4. Do you need Direct Connect or VPN attachments?
5. What's your hybrid cloud connectivity strategy?
6. How will you handle migration from existing solutions?
7. What network management tools will you integrate?

---

## Direct Connect (DX)

### Technical Requirements
1. What bandwidth do you need? (1Gbps, 10Gbps, 100Gbps)
2. How many VPCs need to be connected?
3. Do you require redundancy/high availability?
4. Which AWS regions need connectivity?
5. Will you need public or private virtual interfaces (VIFs), or both?

### Network Architecture
1. What's your existing network topology?
2. Do you need BGP support?
3. Which ASN (Autonomous System Number) will you use?
4. Do you have compatible router equipment?
5. What are your IP addressing requirements?

### Business & Compliance
1. What are your latency requirements?
2. Do you have any compliance/regulatory requirements?
3. Do you require traffic segmentation at the VIF level?
4. What's your disaster recovery strategy?
5. What's your timeline for implementation?
6. Who will manage the Direct Connect connection? (In-house or partner?)

### Location & Physical
1. Which Direct Connect location is closest to your infrastructure?
2. Do you need a Direct Connect Partner to provide last-mile connectivity?
3. Do you have cross-connect capabilities in your facility?

### Security
1. What encryption requirements do you have?
2. Do you need AWS Direct Connect Gateway?
3. What are your network security policies?
4. Who needs access to manage the connection?

### Cost Considerations
1. What's your budget for port hours and data transfer?
2. Do you need committed bandwidth?
3. How long do you need to commit to the connection?

---

## Transit Gateway (TGW)

### Network Architecture
1. How many VPCs need to be connected?
2. What's your cross-region connectivity requirement?
3. Do you need VPN or Direct Connect attachments?
4. What's your routing domain strategy?
5. How will you segment traffic between environments?

### Security & Routing
1. What route table isolation is needed?
2. Do you need inspection architecture integration?
3. What's your traffic flow pattern (hub-spoke, mesh)?
4. How will you implement network segmentation?
5. What's your multicast requirement?

### Performance & Scale
1. What's your expected bandwidth per attachment?
2. How many attachments do you anticipate?
3. What are your latency requirements?
4. Do you need inter-region peering?
5. What's your packet per second requirement?

### Cost Management
1. How will you optimize attachment costs?
2. What's your data transfer pattern?
3. Do you need multiple TGWs for cost allocation?
4. How will you track usage per business unit?

### Operational
1. Who will manage TGW configurations?
2. What's your monitoring strategy?
3. How will you handle route propagation?
4. What's your change management process?

---

## VPC

### Network Architecture
1. What is your total IP address space requirement? (CIDR block)
2. How many subnets do you need across all environments?
3. What's your public/private subnet strategy?
4. How many Availability Zones will you use?
5. Do you need connectivity to existing networks?
6. Are you considering a cellular architecture approach?
7. What's your subnet sizing strategy for future growth?

### Connectivity Requirements
1. What type of internet access is needed?
2. Will you implement VPN or Direct Connect?
3. Do you need VPC peering or Transit Gateway?
4. Which AWS services require VPC endpoints?
5. How many NAT Gateways are required?
6. What's your expected bandwidth consumption?
7. Do you need cross-region connectivity?

### Security Architecture
1. What are your baseline security group requirements?
2. What Network ACL policies are needed?
3. What compliance standards must be met?
4. Which traffic patterns must be controlled?
5. Do you need VPC flow logs?
6. What's your network isolation strategy?
7. How will you secure cross-VPC communication?
8. Do you require traffic inspection?

### Application Requirements
1. What AWS resources will be deployed?
2. What's your load balancer strategy?
3. Are you using containers or serverless?
4. What's the expected traffic volume?
5. Do you need service discovery?
6. What's your application tier separation plan?
7. How will applications communicate between tiers?

### Cost Management
1. What's your NAT Gateway deployment strategy?
2. Which VPC endpoints will provide cost benefits?
3. Do workloads require dedicated tenancy?
4. How will you track costs per environment?
5. What's your resource tagging strategy?
6. How will you optimize data transfer costs?
7. What's your reserved capacity strategy?

### DNS and Routing
1. Will you use AWS or custom DNS?
2. What DHCP options are needed?
3. What's your DNS resolution strategy?
4. How will you manage route tables?
5. Do you need private hosted zones?
6. What's your domain naming strategy?
7. How will you handle cross-VPC DNS?

### Operational Considerations
1. Who owns VPC management?
2. What monitoring solutions are needed?
3. How will you implement backup and DR?
4. What's your change management process?
5. How will you handle maintenance?
6. What logging requirements exist?
7. How will you manage configurations?

### Growth and Scaling
1. What's your CIDR expansion strategy?
2. How will you accommodate new workloads?
3. What's your multi-account strategy?
4. How will you handle mergers/acquisitions?
5. What's your resource scaling approach?
6. How will you manage capacity?
7. What's your environment promotion strategy?

### Network Performance Monitoring
1. What are your baseline performance requirements?
2. Which network paths require active monitoring?
3. What are your critical alerting thresholds?
4. How will you monitor VPC flow logs?
5. What tools will you use for network visibility?
6. How will you track cross-AZ traffic patterns?
7. What's your packet loss and latency tolerance?
8. How will you monitor resource saturation?
9. What's your strategy for troubleshooting network issues?
10. How will you validate security group effectiveness?

---

## VPN

### Connection Requirements
1. Do you need Site-to-Site VPN or Client VPN?
2. What's your required bandwidth capacity?
3. How many site connections are needed?
4. Do you require static or dynamic routing?
5. What's your high availability requirement?

### Technical Specifications
1. What type of customer gateway device will you use?
2. Which routing protocol - static or BGP?
3. What IP ranges need to be routed?
4. Do you need tunnel redundancy?
5. What's your IKE/IPSec configuration?

### Security
1. What encryption requirements do you have?
2. How will you manage security certificates?
3. What's your key rotation strategy?
4. Which authentication methods will you use?
5. What's your access control strategy?

### Operational
1. Who will manage the VPN connections?
2. What's your monitoring approach?
3. How will you handle failover?
4. What's your troubleshooting process?
5. How will you manage configuration changes?

### Cost Considerations
1. How many VPN connections needed?
2. What's your expected data transfer volume?
3. Do you need accelerated VPN?
4. Will you need multiple transit gateways?

### Performance
1. What's your latency requirement?
2. Do you need guaranteed bandwidth?
3. What's your packet loss tolerance?
4. How will you monitor throughput?
5. Do you need AWS Accelerated VPN?

---

## Elastic Load Balancing (ALB, NLB, GWLB)

### Architecture & Type Selection
1. What type of traffic are you load balancing? (HTTP/HTTPS, TCP/UDP, third-party appliances)
2. Do you need Layer 7 (content-based) routing or Layer 4 (connection-based)?
3. Is this internet-facing or internal?
4. How many target groups and backends are expected?
5. Do you need cross-zone load balancing?
6. What's your multi-AZ deployment strategy?
7. Do you need Gateway Load Balancer for inline inspection (third-party appliances)?

### Performance & Scale
1. What's your expected requests per second (RPS)?
2. What's your peak traffic pattern? (steady, spiky, seasonal)
3. Do you need pre-warming for anticipated traffic spikes?
4. What are your connection timeout requirements?
5. What's your expected connection count (concurrent)?
6. Do you need WebSocket or gRPC support?
7. What's your TLS termination strategy?

### Health Checks & Failover
1. What health check criteria define a healthy target?
2. What are your acceptable health check intervals and thresholds?
3. Do you need cross-region failover (Route 53 + multi-region LBs)?
4. How will you handle target deregistration and connection draining?
5. What's your strategy for handling AZ impairments?

### Security
1. What TLS/SSL certificate strategy will you use? (ACM, imported)
2. Do you need mutual TLS (mTLS)?
3. What security policies (TLS versions, ciphers) are required?
4. Do you need WAF integration?
5. What access logging requirements exist?
6. How will you restrict access? (Security groups, prefix lists)

### Cost Management
1. What's your expected LCU/NLCU consumption?
2. How will you optimize idle load balancers?
3. Do you need separate LBs per environment or shared?
4. What's your data processing volume estimate?

### Operational
1. Who manages load balancer configurations?
2. What's your access log analysis strategy?
3. How will you monitor 4xx/5xx error rates?
4. What's your certificate rotation process?
5. How will you handle load balancer scaling events?

---

## AWS Network Firewall

### Architecture
1. Where in the traffic flow does the firewall need to inspect? (ingress, egress, east-west)
2. How many VPCs/regions require firewall inspection?
3. Will you use a centralized inspection VPC or distributed per-VPC firewalls?
4. How will you integrate with Transit Gateway or Cloud WAN service insertion?
5. Do you need symmetric routing for stateful inspection?
6. What's your multi-AZ deployment strategy for firewall endpoints?

### Rule Management
1. What stateless rules are needed? (5-tuple filtering)
2. What stateful rules are needed? (domain filtering, IPS/IDS, protocol detection)
3. Do you need Suricata-compatible rule sets?
4. Will you use managed rule groups (AWS or third-party)?
5. How will you organize rules into rule groups?
6. What's your rule ordering strategy? (strict vs default)
7. How will you handle rule updates and versioning?

### Traffic Patterns
1. What traffic requires inspection? (all, internet-bound only, east-west only)
2. What domains or IPs need to be allowed/denied?
3. Do you need TLS inspection (decryption)?
4. What protocols beyond HTTP/HTTPS need inspection?
5. How will you handle encrypted traffic you cannot inspect?

### Logging & Monitoring
1. What logging destinations will you use? (S3, CloudWatch, Kinesis)
2. Do you need alert-level logs vs. flow-level logs?
3. What SIEM integration is required?
4. How will you monitor firewall capacity and performance?
5. What alerting thresholds are needed for dropped/rejected traffic?

### Performance & Scale
1. What's your expected throughput per AZ?
2. How many concurrent connections do you anticipate?
3. What are your latency requirements for inspected traffic?
4. How will you handle traffic spikes?
5. Do you have any bandwidth-intensive workloads that should bypass inspection?

### Cost Management
1. What's your expected data processing volume?
2. Can you reduce costs by inspecting only specific traffic flows?
3. How will you track firewall costs per business unit?
4. What's your strategy for balancing security coverage vs. cost?

---

## AWS PrivateLink

### Connectivity Requirements
1. Are you a service provider, consumer, or both?
2. What services need to be exposed privately? (your own, third-party, AWS)
3. How many VPCs need access to the endpoint service?
4. Do you need cross-account access?
5. Do you need cross-region access?
6. What's your multi-account/multi-VPC consumption pattern?

### Architecture
1. Will you use interface endpoints (PrivateLink) or gateway endpoints (S3/DynamoDB)?
2. What's your NLB/GWLB backend for the endpoint service?
3. How will you handle DNS resolution for the endpoint? (Private hosted zone, endpoint-specific DNS)
4. Do you need endpoint policies for fine-grained access control?
5. What's your subnet placement strategy for endpoints?
6. How many AZs need endpoint availability?

### Security
1. What endpoint policies are needed to restrict access?
2. How will you control who can create connections to your service?
3. Do you need manual acceptance of connection requests?
4. What security groups will you apply to interface endpoints?
5. How will you audit endpoint usage?

### Performance & Scale
1. How many concurrent connections do you expect per endpoint?
2. What's your bandwidth requirement per AZ?
3. Do you need cross-AZ load balancing at the endpoint level?
4. What are your latency requirements?

### Cost Management
1. How many endpoints and endpoint services do you need?
2. What's your expected data processing volume?
3. Can you consolidate endpoints across services?
4. How will you track PrivateLink costs per team/service?

### Operational
1. Who manages endpoint services vs. endpoint consumers?
2. How will you handle endpoint service versioning/migration?
3. What's your monitoring strategy for endpoint health?
4. How will you troubleshoot connectivity through endpoints?

---

## Route 53 (DNS)

### DNS Architecture
1. Will you use public hosted zones, private hosted zones, or both?
2. How many domains and subdomains do you manage?
3. Do you need split-horizon DNS (different answers for internal vs. external)?
4. What's your cross-account DNS strategy? (centralized vs. distributed)
5. How will VPCs resolve private hosted zones? (associations, RAM sharing)
6. Do you need Route 53 Profiles for multi-VPC/multi-account DNS management?

### Resolver & Hybrid DNS
1. Do you need Route 53 Resolver for hybrid DNS (on-prem ↔ AWS)?
2. What on-premises DNS servers need to resolve AWS resources?
3. What AWS resources need to resolve on-prem domains?
4. How many Resolver inbound/outbound endpoints do you need?
5. What forwarding rules are required?
6. Do you need Resolver DNS Firewall for domain filtering?

### Routing Policies
1. What routing policy do you need? (simple, weighted, latency, geolocation, geoproximity, failover, multivalue)
2. Do you need active-active or active-passive failover?
3. What health checks are needed for DNS failover?
4. How will you implement blue/green deployments via DNS?
5. What TTL strategy will you use?

### Security
1. Do you need DNSSEC for your hosted zones?
2. What Resolver DNS Firewall rules are needed to block malicious domains?
3. How will you protect against DNS exfiltration?
4. Who needs IAM access to manage DNS records?
5. What logging requirements exist? (query logging)

### Performance & Scale
1. How many queries per second do you expect?
2. What latency is acceptable for DNS resolution?
3. Do you need Route 53 Resolver on Outpost for low-latency local resolution?
4. How will you handle DNS caching strategy?

### Operational
1. Who manages DNS records and zones?
2. What's your change management process for DNS changes?
3. How will you automate DNS record creation (IaC, service discovery)?
4. What monitoring/alerting is needed for DNS resolution failures?
5. How will you handle domain registration and renewal?

---

## AWS Global Accelerator

### Use Case & Architecture
1. What's the primary use case? (performance optimization, multi-region failover, static IPs)
2. Do you need static anycast IP addresses?
3. How many AWS regions host your application?
4. What endpoints will you front? (ALB, NLB, EC2, EIP)
5. Do you need custom routing accelerator or standard?
6. What's your client geographic distribution?

### Traffic Management
1. What traffic dial percentage do you need per endpoint group?
2. Do you need endpoint weights within a group?
3. How will you handle regional failover?
4. What health check criteria define healthy endpoints?
5. Do you need client affinity (session stickiness)?
6. What's your blue/green deployment strategy with Global Accelerator?

### Performance
1. What are your latency requirements from client to application?
2. What improvement do you expect vs. public internet routing?
3. What's your expected throughput per accelerator?
4. Do you need TCP or UDP optimization?

### Security
1. Do you need AWS Shield Advanced integration for DDoS protection?
2. How will you restrict access to your accelerators?
3. What flow log requirements exist?
4. Do you need cross-account endpoint support?

### Cost Management
1. How many accelerators do you need?
2. What's your expected data transfer volume through Global Accelerator?
3. What's the cost-benefit vs. CloudFront for your use case?
4. How will you track per-application costs?

### Operational
1. Who manages accelerator configurations?
2. How will you monitor accelerator health and performance?
3. What's your process for adding/removing regions?
4. How will you handle IP address allowlisting with third parties?

---

## NAT Gateway

### Architecture
1. How many NAT Gateways do you need? (per AZ, per VPC)
2. Do you need public NAT (internet access) or private NAT (inter-VPC/on-prem)?
3. What's your multi-AZ redundancy strategy?
4. Which subnets and route tables will point to the NAT Gateway?
5. Do you need connectivity from multiple VPCs through a centralized NAT?

### Performance & Scale
1. What's your expected bandwidth per NAT Gateway? (up to 100 Gbps)
2. How many concurrent connections do you anticipate?
3. What's your packets-per-second requirement?
4. Do you need multiple NAT Gateways for throughput scaling?
5. Are you hitting port allocation limits (55,000 per destination)?

### Security & Compliance
1. Do you need to restrict which resources can access the internet?
2. What logging is required for NAT traffic? (VPC Flow Logs)
3. Do you need static EIPs for allowlisting with external parties?
4. How many EIPs do you need per NAT Gateway?
5. Do you need NAT Gateway in combination with Network Firewall for egress filtering?

### Cost Management
1. What's your expected data processing volume?
2. Can you reduce NAT costs with VPC endpoints for AWS services?
3. What's the cost impact of cross-AZ NAT traffic?
4. Have you considered Gateway Load Balancer + NAT appliances for cost optimization at scale?
5. How will you identify and reduce unnecessary internet-bound traffic?

### Operational
1. Who manages NAT Gateway configuration and EIP allocation?
2. How will you monitor NAT Gateway utilization and connection counts?
3. What alerting is needed for approaching bandwidth/connection limits?
4. How will you handle NAT Gateway maintenance or AZ impairment?
5. What's your strategy if a NAT Gateway becomes a bottleneck?

---

## VPC Peering

### Connectivity Requirements
1. How many VPCs need to be peered?
2. Is peering intra-region or inter-region (or both)?
3. What traffic patterns exist between peered VPCs? (volume, direction)
4. Do the VPC CIDRs overlap? (peering requires non-overlapping CIDRs)
5. Is this a temporary solution or long-term architecture?

### Architecture
1. What's your peering topology? (full mesh, hub-spoke, selective)
2. At what point does TGW become more cost-effective than multiple peerings?
3. How will you manage route tables for peered traffic?
4. Do you need cross-account peering?
5. What about transitive routing needs? (peering is non-transitive)

### Security
1. What security groups will control cross-VPC traffic?
2. Do you need NACLs for additional peering traffic control?
3. How will you audit traffic flowing across peering connections?
4. Who can accept/reject peering requests?

### Cost Management
1. What's your inter-region data transfer volume? (inter-region peering is charged)
2. Is intra-region peering sufficient? (no data transfer charge within same region)
3. At what traffic volume does TGW become cheaper than multiple peering connections?

### Operational
1. Who manages peering connections and route updates?
2. How will you handle CIDR conflicts if VPCs expand?
3. What monitoring is needed for peering connection health?
4. How will you migrate away from peering if you move to TGW/Cloud WAN?
