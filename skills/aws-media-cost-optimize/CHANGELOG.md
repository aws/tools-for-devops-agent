# Changelog

## 1.0.0 (2026-10-27)

- Initial contribution to aws/tools-for-devops-agent: Media Services Cost Optimization.
- Configuration-to-cost layer, threshold gates, misestimation checklist and per service lever references for MediaConnect (flows, Router, reserved outbound bandwidth), MediaLive (input and output rates, reservations, channel class, stop scheduling, input specification right-sizing), MediaPackage v1 and v2, MediaTailor (ad insertion, Channel Assembly, log sampling) and CloudFront delivery economics.
- Pricing data comes from the Price List Query API through the AWS CLI (pricing:DescribeServices and pricing:GetProducts, free). The Price List Bulk API is documented as an operator-run alternative; no script ships with the skill, per the repository's non-executable content rule.
- Description carries explicit boundary routing toward the aws-*-investigate skills and away from general AWS cost review.
- Recommendations only; no purchase, update, stop or delete actions are performed or granted. No Cost Explorer calls.
- Shaped to the DevOps Agent skill-eval best practices: a step checklist the agent copies and ticks, a self-check before findings are presented, and the metric, status and field tables relocated to references/lookup-tables.md so they load only with the step that uses them.
