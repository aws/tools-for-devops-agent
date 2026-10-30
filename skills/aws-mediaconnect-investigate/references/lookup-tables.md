# MediaConnect Deep Investigation: Lookup Tables

Metric catalogs, status tables and field tables relocated from SKILL.md so they load
only when the step that uses them runs. Each heading names the SKILL.md step and
subsection the table belongs to; the surrounding instructions stay in SKILL.md.

## Step 1: Flow state and error messages

| Field | Healthy | Unhealthy | Notes |
|---|---|---|---|
| `Flow.Status` | ACTIVE | STANDBY, ERROR, UPDATING, DELETING | STANDBY = flow not started |
| `Flow.Messages.Errors[]` | Empty array | Non-empty | Active errors — quote verbatim in report |
| `Flow.Source.Transport.Protocol` | Any valid | — | Determines which metrics are emitted |
| `Flow.Source.WhitelistCidr` / `Flow.Source.SenderIpAddress` | Configured | — | For push protocols: verify source IP is expected |

## Step 2: Source connectivity analysis: Protocol-specific metric availability

| Protocol | SourceConnected | ARQ metrics | FEC metrics | RoundTripTime |
|---|---|---|---|---|
| Zixi push/pull | ✅ | ✅ (ARQRequests, ARQRecovered) | ❌ | ✅ |
| SRT caller/listener | ✅ | ✅ (ARQRequests, ARQRecovered) | ❌ | ✅ |
| RIST | ❌ (flow-level `Connected` only) | ✅ | ❌ | ✅ |
| NDI | ✅ (NDI-specific variant¹) | ❌ | ❌ | ❌ |
| RTP | ❌ | ❌ | ✅ (if configured) | ❌ |
| UDP | ❌ | ❌ | ❌ | ❌ |
| CDI | ❌ (CDI payload metrics instead²) | ❌ | ❌ | ❌ |
| ST 2110 JPEG XS | ❌ | ❌ | ❌ | ❌ |

## Step 3: Packet loss analysis (protocol-layered): Layer 1: Raw loss detection

| Metric | Meaning | Severity |
|---|---|---|
| SourcePacketLossPercent | Percentage of packets lost before recovery | Medium if > 0.1% sustained |
| SourceTotalPackets | Total packets received (baseline) | Context metric |
| SourceDroppedPackets | Total packets dropped | Context metric |
| SourceTotalBytes | Total bytes received | Context metric |

## Step 3: Packet loss analysis (protocol-layered): Layer 2: Recovery mechanisms

| Metric | Protocol | Meaning |
|---|---|---|
| SourceRecoveredPackets | All with ARQ/FEC | Packets successfully recovered — NOT an error |
| SourceARQRequests | Zixi, SRT, RIST | ARQ retransmission requests sent upstream |
| SourceARQRecovered | Zixi, SRT, RIST | Packets successfully recovered via ARQ |
| SourceFECPackets | RTP with FEC, Zixi | FEC packets received |
| SourceFECRecovered | RTP with FEC, Zixi | Packets recovered via forward error correction |

## Step 3: Packet loss analysis (protocol-layered): Layer 4: Network path health

| Metric | Protocol | Meaning |
|---|---|---|
| SourceRoundTripTime | Zixi, SRT, RIST | Rising = network congestion or routing change |
| SourceJitter | Most protocols | Rising = network instability |
| SourceLatency | Most protocols | End-to-end source latency |
| SourceARQRequests (rising trend) | Zixi, SRT, RIST | Increasing demand for retransmissions = degrading path |

## Step 3: Packet loss analysis (protocol-layered): CDI-specific loss detection

| Metric | Meaning | Severity |
|---|---|---|
| SourceDroppedPayloads | Payloads lost during transit | High |
| SourceLatePayloads | Payloads arriving outside timing window | Medium |
| SourceTotalPayloads | Total payloads received (baseline) | Context metric |

## Step 4: Transport stream health (TR 101 290): Priority 1 indicators (P1)

| Metric | Meaning | Significance |
|---|---|---|
| ContinuityCounter | TS continuity count errors | Source encoder producing malformed TS |
| PATError | Program Association Table errors | Demux/decode failures downstream |
| PIDError | PID reference errors | PIDs referenced but absent in stream |
| PMTError | Program Map Table errors | Program structure corruption |
| TSByteError | Transport stream byte errors | Byte-level stream corruption |
| TSSyncLoss | Transport stream sync loss | TS sync byte (0x47) not found |

## Step 4: Transport stream health (TR 101 290): Priority 2 indicators (P2)

| Metric | Meaning | Significance |
|---|---|---|
| CATError | Conditional Access Table errors | CA system issues (encrypted content) |
| CRCError | CRC failures | Bit-level corruption (network or source) |
| PCRAccuracyError | PCR accuracy drift | Clock reference drifting beyond tolerance |
| PCRError | Program Clock Reference errors | Clock continuity issues |
| PTSError | Presentation Timestamp errors | Timing issues in content |
| TransportError | Transport error indicator in TS header | Flagged corruption in packet |

## Step 5: Per-output health

| Metric | Statistic | Meaning |
|---|---|---|
| OutputBitrate | Average, Maximum | Should approximately match SourceBitRate |
| OutputConnected | Minimum | 0 = downstream not receiving (SRT/Zixi only) |
| OutputDisconnections | Sum | Any > 0 = output connection was interrupted |
| ConnectedOutputs | Minimum | Flow-level count of connected outputs |

## Step 5: Per-output health (2)

| Metric | Statistic | Meaning |
|---|---|---|
| OutputConnectedReceivers | Minimum | Number of NDI receivers consuming this output |
| OutputGeneratedAudioSamples | Sum | Audio samples generated for NDI output |
| OutputGeneratedVideoFrames | Sum | Video frames generated for NDI output |

## Step 5: Per-output health (3)

| Metric | Meaning | Severity |
|---|---|---|
| OutputDroppedPayloads | Payloads lost in transit | High |
| OutputLatePayloads | Payloads arriving late | Medium |
| OutputTotalPayloads | Total payloads sent (baseline) | Context |
| OutputTotalBytes | Total bytes sent | Context |
