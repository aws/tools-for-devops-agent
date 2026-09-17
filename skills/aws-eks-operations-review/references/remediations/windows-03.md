# Windows remediations — shard 03

Canonical IDs: `W15,W16,W17,W18`

### W15 — EKS-optimized Windows AMI currency
**Why / fix:** Microsoft patches monthly — keep the Windows AMI current and plan node refresh cadence. Link: [Windows patching](https://docs.aws.amazon.com/eks/latest/best-practices/windows-patching.html).

### W16 — Patching strategy
**Why / fix:** Patch Windows Server + container base images; node rotation/expiry covers AMI updates. Link: [Windows patching](https://docs.aws.amazon.com/eks/latest/best-practices/windows-patching.html).

### W17 — Licensing
**Why / fix:** Understand the Windows Server licensing model (included in EC2 Windows pricing). Link: [Windows licensing](https://docs.aws.amazon.com/eks/latest/best-practices/windows-licensing.html).

### W18 — Logging & monitoring agents
**Why / fix:** Deploy Windows-capable agents (Fluent Bit for Windows, CloudWatch agent). Link: [Windows logging](https://docs.aws.amazon.com/eks/latest/best-practices/windows-logging.html).
