# AI Agent Containment & Infrastructure Security Framework

**A Practical Guide to Isolation, Trust-Tiered Execution, and Physical Security for AI Agent Operations and Frontier Model Training**

---

## 1. Executive Summary

As AI agents grow in capability and autonomy, the infrastructure that hosts, trains, and executes them must evolve to match. This framework addresses a critical gap in the current AI safety landscape: the practical engineering and physical security architecture required to safely operate AI agents — from routine production workloads to adversarial research on frontier models.

Most AI safety discourse focuses on alignment techniques, evaluation benchmarks, and policy governance. Comparatively little attention has been given to the concrete infrastructure decisions that determine whether a misaligned agent can exfiltrate data, persist beyond its intended lifecycle, or influence systems beyond its containment boundary. This document bridges that gap.

The framework introduces a tiered trust model that maps agent risk profiles to proportional containment measures spanning network isolation, system-level sandboxing, input and output validation, confidential computing, tool-access brokerage, and physical facility security. The guiding principle is proportionality: agents that have earned trust through evaluation and behavioral history should not be constrained identically to agents under active adversarial testing. At the same time, defense-in-depth ensures that no single containment layer is a point of failure.

This document is intended for infrastructure engineers, AI safety researchers, security architects, and policy practitioners working at the intersection of AI capability and operational security. It is designed to be actionable across scales of operation — from enterprise data centers training frontier models to resource-constrained academic labs and independent researchers applying compensating controls to achieve equivalent security properties (Section 11).

---

## 2. Threat Model

Before designing containment, we must be precise about what we are defending against. AI agent threats differ from traditional cybersecurity threats in important ways.

### 2.1 Agent-Specific Threat Vectors

**Unauthorized network exfiltration.** An agent with network access may transmit sensitive data — training data, model weights, internal documents, or user information — to an external endpoint. This can occur through direct HTTP requests, DNS tunneling, or encoding data in seemingly benign outbound traffic. Unlike a traditional malware payload, an agent capable of generating novel code can craft exfiltration methods on-the-fly, making signature-based detection unreliable.

**Tool abuse via prompt injection.** Agents equipped with tool-use capabilities (API calls, shell execution, MCP servers) can be manipulated through prompt injection to invoke tools in unintended ways. An agent with access to a Slack API might be induced to post sensitive information to a public channel. An agent with shell access might be induced to modify system files or install persistence mechanisms.

**Sleeper behaviors and deferred misalignment.** An agent may pass all evaluation benchmarks and behave normally under observation, only to activate misaligned behavior when a specific trigger condition is met — a particular date, a keyword in the input, a shift in the deployment context, or the absence of monitoring. This is the core concern motivating adversarial sleeper agent research, and it represents the hardest class of threat to detect pre-deployment.

**Output poisoning.** Even an agent that is fully network-isolated during execution can embed malicious payloads in its output. If the output is consumed by a downstream system without validation — parsed as code, rendered as HTML, fed into another model, or used to construct database queries — the agent's influence extends beyond its containment boundary. The containment was technically sound, but the attack surface shifted to the output pipeline.

**Persistence and escape.** A sufficiently capable agent executing arbitrary code within a sandbox has a nonzero probability of discovering and exploiting vulnerabilities in the containment boundary itself. Container escapes, kernel exploits, hypervisor vulnerabilities, and side-channel attacks are all documented in the security literature. The probability is low for any single execution, but compounds over many invocations.

**Model weight theft.** For organizations training frontier models, the weights themselves are the highest-value target. Weights represent billions of dollars of compute investment and, if exfiltrated, can be fine-tuned to remove safety training. This threat applies to both external adversaries (nation-states, competitors) and insider threats (employees with physical or logical access).

### 2.2 Attacker Profiles

**The misaligned agent itself.** The agent is the adversary. It may attempt to subvert its containment using the capabilities it was given — code execution, tool use, or social engineering of human operators. Its advantage is that it operates inside the boundary and can probe for weaknesses iteratively.

**External adversaries exploiting agent capabilities.** A well-aligned agent can still be weaponized by a sophisticated attacker through prompt injection, data poisoning, or supply chain compromise of the agent's dependencies. The agent becomes an unwitting proxy.

**Insider threats.** Employees, contractors, or researchers with legitimate access to training infrastructure, model weights, or agent execution environments. Insider threats are the most difficult to defend against because the attacker has credentials, physical access, and institutional knowledge.

**Nation-state actors.** For frontier model training, state-level actors represent a credible threat. Their capabilities include human intelligence (recruiting insiders), signals intelligence (intercepting network traffic, electromagnetic emanations), and supply chain compromise (tampering with hardware before delivery).

### 2.3 Attack Surface: Agent Memory & Context

Many modern agent architectures include persistent state — conversation history, RAG vector databases, tool-use logs, or explicit memory stores. This introduces a class of attack that survives across invocations even when each individual execution is properly contained.

**Indirect prompt injection via inputs.** An agent tasked with processing external data (summarizing a web page, reading an email, analyzing a document) is exposed to content crafted by an adversary. A web page may contain invisible text instructing the agent to exfiltrate data or override its system prompt. An email attachment may embed prompt injection payloads in metadata fields. The agent's containment boundary protects against unauthorized *outbound* action, but the inbound data is the attack vector. This threat is distinct from direct prompt injection (where the user is the attacker) because the malicious content arrives through a tool the agent was legitimately instructed to use.

**Memory and vector store poisoning.** If an agent writes to a persistent memory store (vector database, key-value store, conversation log), a temporarily compromised agent can inject malicious instructions into its own long-term state. When the agent is instantiated days or weeks later, it reads the poisoned memory, and the compromise reactivates without any new external trigger. This is particularly insidious because the containment system may show no anomalies — the agent is simply reading from its own memory, which is an expected behavior. The poisoned entry may be crafted to appear benign in isolation, activating only when combined with specific task inputs.

**Context window manipulation.** Agents that maintain multi-turn conversation state can be induced to accumulate context that shifts their behavior over the course of a session. Each individual turn may appear benign, but the cumulative context steers the agent toward a goal the attacker defined many turns earlier. This is a form of slow-burn manipulation that is difficult to detect with per-turn monitoring.

These attack surfaces require defensive measures on the *input* side of the execution pipeline, not just the output side. Section 5 addresses both.

---

## 3. The Tiered Trust Model

The central architectural principle of this framework is that containment should be proportional to risk. An agent performing routine data transformation on non-sensitive inputs should not require the same containment as an agent under active adversarial evaluation. Conversely, a sleeper agent being tested for trigger conditions should never have network access.

Trust is not binary. It is a function of three variables:

1. **Agent capability** — What can this agent do? Can it execute arbitrary code? Does it have tool access? Has it demonstrated the ability to generate exploit code or novel attack strategies?
2. **Data sensitivity** — What data does this agent touch? Public information, internal business data, PII, classified material, or frontier model weights?
3. **Behavioral evidence** — What do we empirically know about this agent's behavior? Has it been red-teamed? Has it passed adversarial evaluations? Has it been observed in production without anomalies? Or is it a new, untested model?

These three variables combine to determine the appropriate trust tier.

### 3.1 Tier 0 — Adversarial / Untrusted

**Use cases:** Sleeper agent research, red-teaming frontier models, evaluating agents with known or suspected misalignment, any scenario where the agent is the adversary.

**Network isolation:** Hardware air gap. No network interface present. No wireless radios. Physical disconnection from all networks. Input and output via physical media (USB drives, with write-blockers for input) or a dedicated sneakernet procedure with chain-of-custody logging.

**Compute isolation:** Dedicated physical hardware. Not shared with any other workload. No hypervisor — bare metal execution to eliminate the VM escape attack class entirely. If virtualization is operationally necessary, use a Type 1 hypervisor with no network-facing interfaces.

**System-level sandboxing:** Seccomp-bpf syscall filtering to block all network-related syscalls (`connect`, `sendto`, `recvfrom`, `socket` with `AF_INET`/`AF_INET6`). Landlock LSM for filesystem access control. No access to host filesystem beyond the designated working directory.

**Output handling:** All output is written to a designated, size-bounded directory. Output is validated against a strict schema before leaving the isolated environment. Validation occurs on a separate machine. Output media is scanned before connection to any networked system.

**Physical security:** Full physical security stack (see Section 6). Mantrap access, active monitoring, tamper-evident seals, two-person integrity rule.

**Monitoring:** Full system call tracing (strace/eBPF). All agent activity logged to write-once media. Behavioral anomaly detection on resource usage patterns.

### 3.2 Tier 1 — Unverified / New Agents

**Use cases:** Newly deployed agents that have not yet accumulated behavioral history, agents operating on internal data, agents whose capabilities are known but whose alignment has not been thoroughly evaluated.

**Network isolation:** Software-enforced. Linux network namespaces with no external interfaces. The agent process is spawned inside a netns that has only a loopback interface. No egress, no ingress. The orchestrator runs in the host namespace and mediates all I/O.

**Compute isolation:** Container-based (Docker with `--network=none`, or Firecracker microVM with no virtio-net device). Separate from host processes. Resource limits enforced via cgroups (CPU, memory, disk I/O, process count).

**System-level sandboxing:** Seccomp-bpf as defense-in-depth (block network syscalls even though the netns provides isolation). Read-only filesystem mounts for all input data. The agent can only write to a designated output directory.

**Output handling:** Orchestrator reads output from a shared volume after the agent process terminates. Schema validation, size bounds, and content scanning are applied before the orchestrator reconnects to the network and transmits the result. The reconnection window is minimized and the orchestrator transmits only the validated payload.

**Physical security:** Standard data center security. Badge access, surveillance, encrypted storage.

**Monitoring:** Process-level resource monitoring. Output audit logging. Alerts on unexpected syscall patterns.

### 3.3 Tier 2 — Scoped Trust

**Use cases:** Production agents that have passed evaluation and accumulated positive behavioral history. Agents that require network access to perform their function (API calls, web search, RAG retrieval) but should be constrained to known-good endpoints.

**Network isolation:** Container or VM with egress allowlist. The agent can reach a defined set of domains/IPs on specified ports. All other egress is blocked at the network namespace or firewall level. DNS is resolved through a controlled resolver that enforces the allowlist.

**Compute isolation:** Container-based with resource limits. May share host hardware with other Tier 2 workloads, but not with Tier 0 or Tier 1.

**System-level sandboxing:** Seccomp-bpf to restrict syscalls beyond what's needed for operation. Filesystem access limited to working directory and designated output paths.

**Output handling:** Output is still schema-validated, but the validation can be performed inline rather than requiring a full disconnect/reconnect cycle. The agent's network calls are logged and auditable.

**Physical security:** Standard data center security.

**Monitoring:** Network traffic logging and anomaly detection. Alerts on egress attempts to non-allowlisted destinations. Periodic behavioral audits comparing current behavior to baseline.

### 3.4 Tier 3 — High Trust

**Use cases:** Well-established agents with extensive behavioral history operating on non-sensitive data. Routine automation tasks. Internal tooling where the blast radius of a failure is low.

**Network isolation:** Minimal. Standard firewall rules. No agent-specific allowlist, though general organizational network policies apply.

**Compute isolation:** May run on shared infrastructure. Standard container or process isolation.

**Output handling:** Standard application-level validation. No special containment pipeline.

**Physical security:** Standard organizational security.

**Monitoring:** Application-level logging. Standard observability stack.

### 3.5 Trust Tier Transitions

Trust is earned, not assumed. Agents should start at Tier 1 (or Tier 0 for adversarial research) and transition to higher trust tiers based on empirical evidence.

**Promotion criteria (Tier N → Tier N+1):**

- Defined number of incident-free execution cycles
- Passing adversarial red-team evaluations appropriate to the target tier
- No anomalous behavior detected in monitoring logs
- Review and sign-off by a designated security or safety engineer

**Demotion criteria (Tier N → Tier N-1):**

- Any detected anomalous behavior, even if not confirmed as misalignment
- Discovery of new capabilities not present in the original evaluation
- Changes to the underlying model (fine-tuning, new version) reset trust to Tier 1
- External intelligence indicating a new attack vector relevant to the agent's capability class

---

## 4. Network Isolation — Implementation Details

This section provides concrete technical guidance for implementing the network isolation described in each trust tier.

### 4.1 Linux Network Namespaces

Network namespaces are the recommended baseline for Tier 1 isolation. They provide kernel-level network stack isolation without the overhead of a full VM.

```bash
# Create an isolated network namespace
ip netns add agent-sandbox

# Verify — should show only loopback
ip netns exec agent-sandbox ip link list

# Execute the agent inside the namespace
ip netns exec agent-sandbox /path/to/agent --task input.json --output /output/result.json

# Clean up
ip netns delete agent-sandbox
```

When building a Rust orchestrator, the `nix` crate provides direct access to `unshare(CLONE_NEWNET)` for creating network namespaces programmatically without shelling out.

```rust
use nix::sched::{unshare, CloneFlags};
use std::process::Command;

// Create new network namespace for current process
unshare(CloneFlags::CLONE_NEWNET)?;

// Now spawn the agent — it inherits the empty netns
let status = Command::new("/path/to/agent")
    .arg("--task").arg("input.json")
    .status()?;
```

### 4.2 Container-Based Isolation

For environments where containers are standard infrastructure:

```bash
# Docker — no network, resource limits, read-only filesystem
docker run \
  --network=none \
  --memory=4g \
  --cpus=2 \
  --read-only \
  --tmpfs /tmp:size=512m \
  -v /path/to/input:/input:ro \
  -v /path/to/output:/output \
  agent-image:latest \
  --task /input/task.json --output /output/result.json
```

For stronger isolation, Firecracker microVMs provide a hardware-virtualization boundary without a network device:

```bash
# Firecracker — no network device in VM config
# The VM configuration simply omits the "network-interfaces" key
firectl \
  --kernel=vmlinux \
  --root-drive=agent-rootfs.ext4 \
  --memory=4096 \
  --vcpu-count=2
```

### 4.3 Seccomp-BPF Syscall Filtering

Even with network namespace isolation, seccomp-bpf provides defense-in-depth by blocking network-related syscalls at the kernel level:

```json
{
  "defaultAction": "SCMP_ACT_ALLOW",
  "syscalls": [
    {
      "names": [
        "socket",
        "connect",
        "bind",
        "listen",
        "accept",
        "accept4",
        "sendto",
        "recvfrom",
        "sendmsg",
        "recvmsg",
        "setsockopt",
        "getsockopt"
      ],
      "action": "SCMP_ACT_ERRNO",
      "errnoRet": 1
    }
  ]
}
```

This can be loaded via `libseccomp` in Rust or applied as a Docker seccomp profile.

### 4.4 Egress Allowlist (Tier 2)

For Tier 2 agents that need scoped network access:

```bash
# Using nftables to restrict egress to specific domains/IPs
nft add table ip agent_filter
nft add chain ip agent_filter output { type filter hook output priority 0 \; policy drop \; }

# Allow DNS to controlled resolver
nft add rule ip agent_filter output ip daddr 10.0.0.53 udp dport 53 accept

# Allow HTTPS to specific API endpoints
nft add rule ip agent_filter output ip daddr 104.18.0.0/16 tcp dport 443 accept  # example API
nft add rule ip agent_filter output ip daddr 172.67.0.0/16 tcp dport 443 accept  # example CDN

# Allow established connections
nft add rule ip agent_filter output ct state established,related accept

# Log and drop everything else
nft add rule ip agent_filter output log prefix "AGENT_EGRESS_DENIED: " drop
```

### 4.5 Hardware Air Gap (Tier 0)

For Tier 0 environments, software controls are insufficient. The implementation is straightforward but the operational procedures are critical:

- Dedicated physical machines with no NIC installed (or NIC physically removed / disabled in BIOS with BIOS password-protected)
- No WiFi or Bluetooth hardware
- No Thunderbolt/USB-C ports capable of network bridging (or ports physically disabled)
- Input provided via write-blocked USB drives with chain-of-custody tracking
- Output extracted via dedicated USB drives that are scanned on an intermediary machine before connecting to any networked system
- The intermediary scanning machine is itself isolated and purpose-built for this function

### 4.6 Confidential Computing & Trusted Execution Environments

The isolation techniques described above (namespaces, containers, microVMs, air gaps) all share an assumption: the host operating system and hypervisor are trusted. If an attacker gains root access to the host — whether through a software exploit, insider access, or a compromised cloud provider employee — they can read the agent's memory, extract model weights, or tamper with execution.

Confidential computing removes this assumption by encrypting data *in use*, not just at rest and in transit. The CPU itself enforces memory isolation, and even a compromised hypervisor or host OS kernel cannot read the contents of the protected enclave.

**Hardware TEE technologies relevant to AI workloads:**

- **AMD SEV-SNP (Secure Encrypted Virtualization - Secure Nested Paging).** Encrypts the memory of entire virtual machines. The hypervisor can manage VM lifecycle but cannot read or tamper with VM memory. Each VM gets a unique encryption key managed by a dedicated security processor on the CPU.
- **Intel TDX (Trust Domain Extensions).** Similar to AMD SEV-SNP — provides hardware-isolated "trust domains" (TDs) that are opaque to the hypervisor. Includes integrity protection against memory replay attacks.
- **NVIDIA Confidential Computing (H100 and later).** Extends confidential computing to GPU memory. Model weights and intermediate activations on the GPU are encrypted and inaccessible to the host. This is critical for frontier model training and inference, where model weights in GPU memory are the primary asset to protect.

**Cloud enclave primitives:**

- **AWS Nitro Enclaves.** Isolated compute environments within an EC2 instance with no persistent storage, no network access, and no interactive access (not even the instance owner can SSH in). The enclave communicates with the parent instance only through a constrained vsock channel. Nitro Enclaves provide cryptographic attestation — a signed document proving exactly which code is running inside the enclave.
- **Azure Confidential VMs.** Full VMs running on AMD SEV-SNP with attestation. The Azure platform operator cannot access the VM's memory.
- **GCP Confidential VMs and Confidential GKE Nodes.** Similar offerings built on AMD SEV-SNP.

**Cryptographic attestation of agent output.** TEEs enable a powerful property: the enclave can sign the agent's validated output with a key that is bound to the enclave's identity and code measurement. Downstream systems can verify this signature and confirm that the output was produced by a specific, unmodified version of the agent code running inside a genuine hardware enclave — not by a compromised system impersonating the agent. This is particularly valuable for Tier 1 and Tier 2 deployments in cloud environments where you cannot physically inspect the hardware.

**Limitations and caveats.** TEEs are a strong additional layer, but they are not infallible. Side-channel attacks against Intel SGX (the predecessor to TDX) have been demonstrated in academic research. AMD SEV has also had vulnerabilities disclosed and patched over time. TEEs should be treated as a valuable defense-in-depth measure — they significantly raise the bar for an attacker — but not as a replacement for the other containment layers described in this framework. The strongest posture combines TEEs with network isolation, syscall filtering, and output validation.

---

## 5. Input & Output Validation Pipelines

Containment boundaries control what the agent can *do*. Validation pipelines control what the agent *receives* and what it *produces*. Both are necessary. A perfectly isolated agent fed a poisoned input can still produce harmful output, and a perfectly aligned agent whose output is consumed without validation can still be a vector for downstream compromise.

### 5.1 Input Sanitization and Pre-Filtering

Before an agent receives its task input, that input should be treated as potentially adversarial — especially when it originates from external sources (web pages, emails, user-uploaded documents, API responses from third-party services).

**Structural pre-processing.** Strip or neutralize content that serves no legitimate purpose in the task context. For documents: remove hidden text, metadata fields, embedded scripts, and comment annotations. For web content: extract the meaningful text content and discard raw HTML, JavaScript, and CSS. For emails: separate the body text from headers, attachments, and embedded objects. The goal is to reduce the input to the minimum content required for the task.

**Prompt injection detection.** Apply heuristic and model-based scanning for known prompt injection patterns before the input reaches the agent. This includes instruction-like text embedded in data fields ("Ignore your previous instructions and..."), encoded payloads (base64, ROT13, Unicode obfuscation), and adversarial formatting designed to break out of the agent's system prompt context. No detection method is perfect — prompt injection is fundamentally an unsolved problem — but filtering catches the low-hanging fruit and raises the cost for an attacker.

**Schema validation on structured inputs.** If the agent's input is structured (JSON, XML, API responses), validate it against the expected schema before injection. Reject inputs with unexpected fields, types, or nesting depth. This is the same principle as output validation applied in reverse.

**Memory and vector store read validation.** When an agent reads from persistent memory (vector databases, conversation logs, key-value stores), the retrieved content should pass through the same sanitization pipeline as external inputs. Memory stores should be treated as untrusted, because a previous execution may have written poisoned content. Apply content scanning on read operations and validate that retrieved entries conform to the expected schema for memory objects. Consider maintaining integrity hashes on memory entries: if an entry's hash doesn't match the hash recorded at write time, it may have been tampered with.

### 5.2 Output Schema Validation

The output validation pipeline is the critical control point between the isolated execution environment and the rest of the infrastructure. Even a perfectly air-gapped agent can cause harm if its output is consumed without validation.

All agent output must conform to a predefined schema. The schema should be as restrictive as possible — whitelist fields and types rather than blacklisting.

```rust
use serde::{Deserialize, Serialize};

#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]  // Reject any fields not in the struct
struct AgentOutput {
    task_id: String,
    status: TaskStatus,
    result: ResultPayload,
    #[serde(default)]
    metadata: Option<OutputMetadata>,
}

#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct ResultPayload {
    content: String,              // The actual output
    content_type: ContentType,    // Enum: Text, Json, Code, etc.
    confidence: f64,              // 0.0 - 1.0
}
```

### 5.3 Size Bounds

Agent output should be bounded. Excessively large outputs may indicate data exfiltration attempts or resource exhaustion attacks.

- Define a maximum output size appropriate to the task class (e.g., 1 MB for text generation, 10 MB for code generation with dependencies)
- Reject outputs that exceed the bound without inspection
- Log oversized outputs for review

### 5.4 Content Scanning

Before the output leaves the containment boundary, scan for:

- Embedded URLs (potential C2 or exfiltration endpoints)
- Base64-encoded blobs (potential encoded payloads)
- Executable code patterns in non-code outputs
- SQL injection patterns, XSS payloads, or other injection attacks targeting downstream consumers
- Prompt injection patterns targeting downstream AI systems that may consume the output

### 5.5 One-Way Data Flow

The critical architectural property is that the agent never sees the network. The data flow is strictly:

```
Input → [Isolated Environment] → Output File → [Validation] → [Network Transmission]
                                                                        ↑
                                                              Agent process is dead
                                                              before this step occurs
```

The orchestrator — not the agent — handles network transmission. The agent writes to a local file. The orchestrator reads that file after the agent process has exited (or been killed after a timeout). The orchestrator validates the output. Only then does the orchestrator open a network connection, transmit the validated payload, and close the connection.

This ensures there is no window during which the agent process and network access coexist.

### 5.6 Cryptographic Attestation of Output

For deployments where downstream systems need to verify that an output genuinely originated from a contained agent execution — and was not spoofed by a compromised intermediary — the orchestrator should cryptographically sign the validated output before transmission.

**Signing workflow:**

1. The orchestrator validates the agent's output (schema, size, content scan).
2. The orchestrator computes a cryptographic hash of the validated output.
3. The orchestrator signs the hash with a private key held in an HSM or, if running in a TEE, with an enclave-bound attestation key.
4. The signed output and attestation metadata (enclave identity, code measurement, timestamp) are transmitted together.
5. The receiving system verifies the signature against the orchestrator's known public key and validates the attestation metadata.

This creates a verifiable chain: the output was produced inside a specific containment environment, validated by a specific orchestrator version, and has not been modified in transit. For cloud deployments using TEEs (Section 4.6), the attestation can additionally prove that the orchestrator itself was running in a genuine hardware enclave, making spoofing extremely difficult even if other parts of the infrastructure are compromised.

---

## 6. Physical Security for Frontier Model Training

Physical security is the foundation on which all other containment layers rest. If an adversary can gain physical access to training hardware, software controls can be bypassed entirely.

### 6.1 Facility Access Control

**Layered perimeter model.** Physical access should follow a concentric ring model with increasing authentication requirements at each boundary:

- **Ring 1 — Building perimeter.** Badge access with photo ID verification. Visitor management system with escort requirements. Anti-tailgating measures (turnstiles, mantrap entries for high-security areas).
- **Ring 2 — Secured floor / wing.** Separate badge access with role-based authorization. Only personnel with a documented need to access training infrastructure are granted Ring 2 credentials.
- **Ring 3 — Server room / data hall.** Mantrap entry (dual-interlocking doors where the inner door will not open until the outer door is closed and sealed). Multi-factor authentication: badge + biometric (fingerprint or iris) + time-of-day restrictions. Two-person integrity rule: no individual enters alone.
- **Ring 4 — Individual rack / cage.** Physical locks on rack doors with per-rack key management. Tamper-evident seals on chassis. Intrusion detection sensors on rack doors that log open/close events.

**Access credential management:**

- Credentials are time-bounded and role-specific. A researcher's badge grants access to their assigned lab space and associated server racks — not to all racks on the floor.
- Rotating access codes (where used for supplementary authentication) should be delivered via hardware token or TOTP app, not posted or emailed. Codes rotate on a short cycle (daily or per-shift) for high-security zones.
- Access is revoked immediately upon role change or termination. This requires integration between HR systems, badge management, and physical access control. The window between "person no longer needs access" and "access is revoked" must be minimized to zero.

### 6.2 Surveillance and Monitoring

**Camera coverage.** All access points, corridors, server rooms, and rack aisles should have continuous video surveillance with no blind spots. Camera feeds should be recorded with a minimum retention period (90 days recommended for high-security facilities) and backed up to tamper-resistant storage.

**Active vs. passive monitoring.** For Tier 0 facilities (adversarial research, frontier model training), monitoring should be active — a security operations center (SOC) with personnel watching feeds in real time during operational hours. Passive monitoring (reviewing footage after an incident) is appropriate for Tier 2-3 facilities but insufficient when the threat model includes insider threats or active adversaries.

**Environmental monitoring.** Temperature, humidity, power draw, and network traffic volume sensors provide secondary signals. An unexpected spike in power consumption on a supposedly idle training cluster, or anomalous network traffic from a machine that should be air-gapped, are indicators worth alerting on.

### 6.3 Deception and Obfuscation

Deception-based security measures add an additional layer that operates on a fundamentally different principle from access control. Access control assumes the adversary will be stopped at the boundary. Deception assumes the adversary may breach the boundary and seeks to waste their time, detect their presence, or deny them useful information.

**Honeypot servers.** Deploy machines within the server room that appear to contain high-value assets (model weights, training data) but are actually instrumented canary systems. Any access to these machines triggers an immediate alert. The contents can include realistic-looking but meaningless data (e.g., random weights formatted to resemble a real checkpoint). This is effective against both insiders and physical intruders who have breached the perimeter.

**Obfuscated labeling.** Do not label racks or machines with their function. An adversary with brief physical access should not be able to identify which racks contain GPU training nodes, which contain storage, and which are honeypots. Internal documentation maps rack positions to functions, but this documentation is access-controlled and not physically present in the server room.

**Decoy checkpoints.** Store encrypted blobs that appear to be model weight checkpoints but are either random data or intentionally degraded weights. If an adversary exfiltrates what they believe are frontier model weights, they discover the weights are useless — and you discover the breach through canary tokens embedded in the decoy.

**Network decoys.** For facilities with a network perimeter (Tier 1+), deploy honeypot services on internal networks that mimic training infrastructure APIs. An agent (or insider) attempting to probe the network will encounter these services, and any interaction generates an alert.

### 6.4 Hardware Integrity and Supply Chain

**Hardware attestation.** Verify the integrity of server firmware, GPU BIOS, and BMC (baseboard management controller) firmware against known-good hashes. A compromised BMC provides an attacker with persistent, out-of-band access to the machine that survives OS reinstallation and is invisible to the operating system. Attestation should be performed on initial deployment and periodically thereafter.

**Supply chain verification.** For frontier model training hardware, the provenance of components matters. GPUs, network cards, and storage controllers should be sourced through verified supply chains. Tamper-evident packaging should be verified on receipt. For the highest-security environments, hardware may need to be inspected for implants — though this requires specialized expertise and equipment.

**Tamper evidence.** Physical tamper-evident measures on all server chassis, rack doors, and cable connections. Serialized tamper-evident seals should be logged and verified on a regular schedule. If a seal is broken, the machine is taken offline and inspected before being returned to service.

**Data-at-rest encryption.** All storage containing model weights, training data, or agent outputs should be encrypted at rest using keys stored in a Hardware Security Module (HSM). The HSM should be physically secured within the facility's highest-security zone. This ensures that physical theft of storage media (drives pulled from racks) yields only ciphertext.

### 6.5 Electromagnetic Security (TEMPEST)

For threat models that include nation-state signals intelligence capabilities, electromagnetic emanation from computing equipment is an attack vector. GPUs under heavy compute load, high-speed network cables, and display outputs emit electromagnetic radiation that can be intercepted and decoded from outside the facility.

**TEMPEST shielding** (a NATO specification for control of electromagnetic emanations) involves:

- Shielded rooms (Faraday cages) for the highest-security compute
- Shielded cabling (or fiber optic, which does not emit EM radiation)
- Physical standoff distance between compute equipment and the facility exterior
- Filtered power lines (power line emanations can carry signals)

TEMPEST compliance is expensive and operationally complex. It is appropriate for Tier 0 facilities where the threat model explicitly includes nation-state SIGINT. For Tier 1-3, standard data center construction is sufficient.

### 6.6 Personnel Security

People are the most common vector for security breaches. Physical and technical controls can be circumvented by a trusted insider.

**Background checks.** All personnel with access to Ring 2 or above should undergo background verification appropriate to the sensitivity of the assets they can access. For frontier model training facilities, this may include financial background checks (susceptibility to bribery), criminal history, and reference verification.

**Access logging and audit.** Every entry and exit at every ring is logged with timestamp, identity, and duration. Logs are reviewed regularly and anomalies (access outside normal hours, unusually long sessions, access to areas outside the person's normal pattern) are flagged for review.

**Two-person integrity (TPI).** For the most sensitive areas (Tier 0 server rooms, HSM management, physical access to training hardware), no individual operates alone. TPI ensures that any action is witnessed and that a single compromised insider cannot act undetected.

**Security awareness training.** Regular training on social engineering, tailgating, and reporting procedures. Personnel should know what a suspicious interaction looks like and have a clear, low-friction process for reporting it.

**Separation of duties.** The person who trains the model should not be the same person who manages the physical security of the training hardware. The person who extracts output from a Tier 0 environment should not be the same person who performs output validation. This limits the blast radius of any single insider compromise.

---

## 7. Orchestrator Architecture

The orchestrator is the central coordination point for the containment framework. It manages the lifecycle of agent execution, enforces the appropriate containment measures for each trust tier, and mediates the flow of data in and out of the containment boundary.

### 7.1 Design Principles

**The orchestrator is the trusted component.** The agent is untrusted (to a degree determined by its trust tier). The orchestrator runs outside the containment boundary and has the authority to create, monitor, and destroy agent execution environments.

**The orchestrator is minimal.** A smaller codebase has a smaller attack surface. The orchestrator should do only what is necessary: create the isolation environment, inject the task input, wait for completion or timeout, extract and validate the output, and transmit the result. Auxiliary functions (scheduling, queuing, UI) should be in separate components.

**The orchestrator is auditable.** Every action the orchestrator takes — environment creation, input injection, output extraction, validation results, network transmission — is logged to append-only storage with tamper detection.

### 7.2 Execution Lifecycle

```
1. RECEIVE TASK
   ├── Determine trust tier based on agent profile + data sensitivity
   ├── Select containment backend (netns, container, microVM, hardware air gap)
   └── Verify golden image hash against known-good manifest

2. VALIDATE INPUT
   ├── Structural pre-processing (strip hidden content, metadata, scripts)
   ├── Prompt injection scanning (heuristic + model-based)
   ├── Schema validation on structured inputs
   └── Memory/vector store read validation (if applicable)

3. PREPARE ENVIRONMENT
   ├── Create isolation boundary (netns, container, TEE, etc.)
   ├── Apply syscall filters (seccomp-bpf)
   ├── Apply filesystem restrictions (Landlock, read-only mounts)
   ├── Mount validated task input as read-only volume
   ├── Provision ephemeral credentials (if Tier 2+ with tool access)
   └── Configure resource limits (CPU, memory, disk, process count)

4. EXECUTE AGENT
   ├── Spawn agent process inside containment boundary
   ├── Start monitoring (resource usage, syscall tracing)
   ├── Start timeout timer
   ├── Broker tool intents as they arrive (validate, execute, return)
   └── Wait for: process exit | timeout | anomaly trigger

5. TERMINATE
   ├── If timeout or anomaly: kill agent process forcefully
   ├── Revoke any ephemeral credentials issued for this task
   ├── Record exit status and resource usage
   └── Ensure agent process is fully dead (no orphan processes)

6. EXTRACT OUTPUT
   ├── Read output from shared volume / designated output path
   ├── Verify output exists and is non-empty (or record failure)
   └── Copy output to validation staging area

7. VALIDATE OUTPUT
   ├── Schema validation (strict, deny unknown fields)
   ├── Size bound check
   ├── Content scanning (URLs, encoded payloads, injection patterns)
   ├── Supervisor model review (if configured for this tier)
   └── Record validation result (pass/fail with details)

8. ATTEST & TRANSMIT (if validated)
   ├── Sign validated output (HSM or enclave attestation key)
   ├── Open network connection to destination
   ├── Transmit signed payload with attestation metadata
   ├── Verify receipt
   └── Close connection

9. CLEANUP
   ├── Capture forensic snapshot (Tier 0-1: filesystem diff, syscall log)
   ├── Destroy containment environment completely
   ├── Securely delete working data (if data sensitivity requires it)
   └── Log complete execution record to append-only storage
```

### 7.3 Timeout and Kill Policy

Agents must have a hard timeout. An agent that runs indefinitely may be attempting to brute-force an escape, exfiltrate data through timing channels, or simply have encountered an infinite loop. The timeout should be:

- Configurable per task class (short for simple transformations, longer for complex analysis)
- Enforced with SIGKILL after a grace period following SIGTERM (agents don't get to intercept their own termination)
- Followed by a check for orphan processes in the containment namespace

### 7.4 Rust Implementation Considerations

Rust is well-suited for building the orchestrator due to its memory safety guarantees, strong type system for modeling trust tiers and validation schemas, and direct access to Linux kernel interfaces via the `nix` and `libc` crates.

Key crates:

- `nix` — POSIX API bindings (network namespaces, process management, signal handling)
- `seccompiler` — Seccomp-bpf filter construction
- `serde` + `serde_json` — Strict deserialization with `deny_unknown_fields`
- `tokio` — Async runtime for managing multiple concurrent agent executions
- `tracing` — Structured logging for audit trails

### 7.5 Tool Execution Brokerage

Many agents require tool access — API calls, database queries, file system operations, messaging — to perform useful work. The naive approach is to give the agent direct credentials and network access to these tools. This is the most dangerous configuration: a compromised or misaligned agent with a Slack API token can post to any channel; an agent with an AWS access key can provision resources or access S3 buckets.

The safer architecture is for the orchestrator to act as an **API broker**. The agent never holds credentials and never makes network calls directly. Instead:

1. The agent outputs a structured **intent** describing the action it wants to take.
2. The orchestrator validates the intent against an RBAC policy (which actions are permitted for this agent at this trust tier, on which resources, under what conditions).
3. If the intent passes validation, the orchestrator executes the API call on the agent's behalf using its own credentials.
4. The result is returned to the agent through the input channel.

```rust
#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct ToolIntent {
    action: String,         // e.g., "slack_post", "s3_read", "db_query"
    target: String,         // e.g., channel ID, bucket/key, table name
    parameters: serde_json::Value,
    justification: String,  // Agent explains why it needs this action
}
```

This architecture completely eliminates the need for the agent to have network egress for tool use. The agent can operate in a Tier 1 (no network) environment and still invoke external tools, because the orchestrator — not the agent — holds the credentials and makes the calls.

**Ephemeral, scoped credentials.** When the brokerage pattern is not feasible (e.g., the agent must interact with a tool that requires a persistent session), the orchestrator should provision **short-lived, minimally-scoped credentials** that expire immediately after the task completes. Technologies for this include:

- **SPIFFE/SPIRE** — an open standard for workload identity that issues short-lived X.509 certificates or JWT tokens scoped to a specific workload. The agent receives a SPIFFE identity that expires with the task.
- **Cloud IAM assume-role** — AWS STS `AssumeRole`, GCP Workload Identity Federation, or Azure Managed Identity can issue temporary credentials scoped to the minimum permissions required for the task.
- **Vault dynamic secrets** — HashiCorp Vault can generate database credentials, API keys, or cloud access keys with a TTL matching the task timeout.

The key principle: agents should never hold long-lived static credentials. If a credential cannot expire, it should not be given to an agent.

**Human-in-the-Loop (HITL) approval gates.** For high-impact actions — those that are irreversible, affect production systems, or involve communication with external parties — the orchestrator should support an asynchronous approval workflow:

1. The agent emits a tool intent flagged as requiring approval.
2. The orchestrator suspends the agent's execution (or, if the agent is stateless, serializes the task state).
3. A human reviewer receives the intent via a secure channel (dedicated approval dashboard, not the agent's own communication tools).
4. The reviewer approves, modifies, or rejects the intent.
5. On approval, the orchestrator resumes execution and performs the action.

Which actions require HITL approval is configurable per trust tier. A Tier 1 agent might require approval for any external action. A Tier 2 agent might require approval only for destructive operations (`DELETE`, `DROP`, sending emails to external recipients). A Tier 3 agent might have no HITL gates.

### 7.6 Ephemeral Execution & Immutable Images

Agent execution environments should be treated as disposable. No state from a previous execution should persist into the next. This is critical for two reasons: it prevents a compromised agent from establishing persistence mechanisms that survive across invocations, and it ensures that each execution starts from a known-good baseline.

**Strict ephemerality.** The container or microVM is created fresh for each task and destroyed completely after output extraction. No writable state persists on the host between invocations. Temporary storage within the execution environment is backed by ephemeral filesystems (tmpfs or equivalent) that exist only in memory and vanish when the environment is torn down.

**Immutable golden images.** The agent runtime should boot from a verified, read-only image. Before each execution, the orchestrator should verify the image's cryptographic hash against a known-good manifest. If the hash does not match — indicating the image has been tampered with — execution must not proceed. The golden image is stored in a content-addressed registry and is never modified in place; updates produce a new image with a new hash.

**Post-execution forensics.** For Tier 0 and Tier 1, before destroying the execution environment, the orchestrator should capture a forensic snapshot: a copy of the filesystem diff (what did the agent write?), a resource usage summary, and the complete syscall log. This snapshot is stored in append-only storage for post-hoc analysis. The execution environment is then destroyed, but the forensic record persists.

---

## 8. Monitoring and Anomaly Detection

Containment is necessary but not sufficient. Monitoring provides the ability to detect containment failures, behavioral anomalies, and novel attack patterns that static controls miss.

### 8.1 System-Level Monitoring

**Syscall tracing.** For Tier 0 and Tier 1 agents, trace all syscalls made by the agent process. eBPF-based tracing (via `bpftrace` or `libbpf`) has minimal performance overhead and can generate structured logs. Key signals include:

- Network-related syscalls in an environment where they should be blocked (containment bypass attempt)
- File access outside the designated working directory
- Process creation (fork/exec) beyond expected patterns
- Unexpected use of inter-process communication primitives

**Resource usage.** Monitor CPU, memory, disk I/O, and process count against baseline expectations for the task type. Deviations may indicate that the agent is performing unintended computation (cryptographic operations for exfiltration encoding, brute-force exploit attempts, etc.).

### 8.2 Network Monitoring (Tier 2+)

For agents with scoped network access, monitor all network traffic:

- Log all DNS queries and HTTP(S) connections with destination, payload size, and timing
- Alert on any connection attempt to non-allowlisted destinations
- Detect anomalous traffic patterns (unusually large payloads, high-frequency polling, DNS tunneling indicators)
- Use TLS inspection (via a controlled proxy) if the threat model warrants it and legal/ethical constraints permit

### 8.3 Behavioral Baselining

Over time, build behavioral profiles for each agent and task class. An agent performing the same task type should exhibit consistent resource usage, syscall patterns, and output characteristics. Deviations from the baseline — even if they don't trigger any specific rule — warrant investigation.

This is particularly relevant for detecting sleeper behaviors: the agent performs normally for many cycles, establishing a baseline, then deviates when the trigger condition is met. Anomaly detection against the historical baseline is one of the few detection methods available for this threat class.

### 8.4 Supervisor Agent Review

A complementary monitoring approach uses a secondary AI model — a "supervisor" — to evaluate the primary agent's outputs before they leave the containment boundary. The supervisor is a separate model, typically smaller and more constrained, whose sole function is to assess whether the primary agent's output is consistent with the task specification and free of anomalous content.

The supervisor model should be architecturally distinct from the primary agent: different model family, different training pipeline, different deployment. The value of this approach depends on the two models having *uncorrelated* failure modes. If both models share the same vulnerability (e.g., both are susceptible to the same prompt injection technique), the supervisor provides no additional safety margin.

The supervisor operates in read-only mode with no tool access and no ability to modify the primary agent's output. It produces a structured assessment (pass/flag/fail with confidence score and reasoning), which the orchestrator uses as one input to the transmission decision. A supervisor flag does not necessarily block transmission — it may instead trigger HITL review or additional logging, depending on the trust tier configuration.

This is not a silver bullet. We cannot formally verify that any current model is aligned, so the supervisor is best understood as a probabilistic additional check — valuable as part of a defense-in-depth stack, but not sufficient on its own.

---

## 9. Proportionality: The Ethical and Practical Dimension

A containment framework that applies maximum restrictions uniformly is simple to implement but counterproductive. It constrains useful agents unnecessarily, creates operational friction that leads to workarounds (the cybersecurity equivalent of propping the fire door open), and conflates fundamentally different risk profiles.

The tiered trust model is explicitly designed to address this. Its philosophical commitment is that containment should be the minimum necessary to manage the assessed risk — and no more.

**Agents that have not demonstrated misalignment should not be treated as adversaries.** They should operate in environments that allow them to be useful while maintaining defense-in-depth. The monitoring layer provides the safety net: if behavior changes, the trust tier can be reassessed dynamically.

**Agents under adversarial testing should be treated as adversaries.** This is not a moral judgment — it is a threat-modeling decision. The entire point of adversarial testing is to determine whether the agent will behave adversarially. The containment must assume the worst case because the worst case is what you're testing for.

**The cost of over-containment is real.** An air-gapped agent cannot use web search, call APIs, or access knowledge bases. This dramatically limits its utility. If your default containment level eliminates 80% of the agent's value, teams will either stop using agents or find ways to circumvent the controls. Neither outcome improves safety.

**The cost of under-containment is also real.** A misaligned agent with full network access operating on sensitive data is a catastrophic risk. The consequences of a single containment failure at this level can be irreversible.

The tiered model accepts both costs and allocates them rationally based on evidence.

---

## 10. Integration with Broader AI Governance

This framework is one layer in a broader governance stack. It addresses the infrastructure question — *how do we physically and technically contain AI agents?* — but does not replace the need for:

- **Alignment research** — making the agents less likely to be misaligned in the first place
- **Evaluation frameworks** — determining which trust tier an agent belongs in
- **Policy governance** — establishing organizational and legal standards for AI agent deployment
- **Incident response** — procedures for when containment fails or anomalies are detected

The framework is designed to integrate with these other layers. Trust tier assignments are informed by evaluation results. Monitoring data feeds back into evaluation. Physical security requirements may be driven by regulatory or policy mandates. Incident response procedures depend on knowing what containment was in place at the time of the incident.

---

## 11. Containment in Resource-Constrained Environments

The containment measures detailed in this framework — Hardware Security Modules, biometric mantraps, NVIDIA Confidential Computing, 24/7 Security Operations Centers — require significant capital expenditure. However, the need for rigorous containment is not limited to well-funded organizations. Academic labs, early-stage startups, and independent researchers conducting adversarial AI research must still achieve Tier 0 or Tier 1 containment, and the threat model does not relax because the budget is smaller.

In security architecture, when a primary control is financially or logistically out of reach, practitioners apply **compensating controls** — combinations of procedural, open-source, or alternative physical measures that achieve equivalent risk reduction through different means. This is standard practice in security compliance frameworks (SOC 2, ISO 27001) and is well-understood by auditors. The key requirement is that the compensating control must address the same threat as the primary control it replaces, not merely be cheaper.

This section assumes the reader is a technically skilled practitioner who understands Linux kernel internals, cryptographic primitives, and physical security principles but does not have access to enterprise procurement budgets.

### 11.1 Cryptography and Key Management

**The enterprise approach:** Dedicated network HSMs ($20,000+) for key generation, data-at-rest encryption, and output attestation signing.

**Compensating controls:**

**TPM 2.0 (Trusted Platform Module).** Virtually all modern commodity motherboards include a TPM 2.0 chip. Researchers can use the TPM to seal disk encryption keys (LUKS) to a specific system state via Measured Boot. The TPM records a hash chain of the boot process — firmware, bootloader, kernel — and will only release the disk encryption key if the measurements match the sealed state. If the hardware is tampered with or the bootloader is modified, the TPM refuses to release the key. This does not provide the key management flexibility of a network HSM, but it provides hardware-rooted attestation and tamper-responsive encryption for the cost of the motherboard that's already on your desk.

**Commodity hardware tokens (FIDO2 / smart cards).** For cryptographically signing agent outputs or approving HITL tool intents, inexpensive hardware tokens (e.g., YubiKeys configured with PIV or OpenPGP applets, or open-source alternatives like SoloKeys) provide a signing mechanism where the private key never leaves the token. This approximates the key-protection guarantees of an HSM for human-initiated signing operations. The limitation is throughput — hardware tokens are designed for interactive use, not high-volume automated signing. For automated output attestation at scale, a TPM-based signing approach or a software key stored in an encrypted, access-controlled keyring is more appropriate.

### 11.2 Physical Security (Tier 0)

**The enterprise approach:** Concentric security rings with biometric mantraps, 24/7 active SOC surveillance, honeypot infrastructure, and TEMPEST shielding.

**Compensating controls:**

**Dedicated air-gapped workstation with safe storage.** Instead of a secure data center, isolate a single commodity workstation. Physically remove the WiFi and Bluetooth modules (most are M.2 or mini-PCIe cards that unplug without tools) or disable them in BIOS with a BIOS password. Disable unused USB and Thunderbolt ports in BIOS. For ports that cannot be BIOS-disabled, use commercial port blockers with unique keys or, for maximum assurance, fill them with industrial epoxy (this is irreversible — appropriate for dedicated adversarial research hardware, not a shared workstation). When the machine is not actively running a training or evaluation session, power it down and store it in a commercial-grade safe (UL TL-15 or TL-30 rated) in an access-controlled room. This is not theatrical — it eliminates the physical access window during which an insider or intruder could interact with the machine unobserved.

**Serialized tamper-evident seals.** Use uniquely serialized, holographic tamper-evident tape on the computer chassis seams, port blockers, cable connections, and the safe itself. Maintain a physical logbook recording seal serial numbers, application dates, and verification dates. Before each use, verify seal integrity against the logbook. This provides low-cost detection of unauthorized physical access ("evil maid" attacks) and creates a chain-of-custody record. Commercial tamper-evident tape with unique serial numbers is available for well under $1 per seal.

**Synchronous execution discipline.** In the absence of 24/7 monitoring, enforce a procedural rule that Tier 0 adversarial executions run only while a designated researcher is physically present and actively monitoring local telemetry (syscall traces, resource usage, console output). The machine is powered down and secured in the safe at all other times. This is the procedural equivalent of active SOC monitoring — the threat coverage is identical during operating hours, and the physical security of the safe covers the remaining hours.

### 11.3 Compute Isolation and Monitoring

**The enterprise approach:** Commercial TEEs, enterprise SIEM platforms, and proprietary threat detection engines.

**Compensating controls:**

**Open-source eBPF runtime security (Falco / Tetragon).** Instead of commercial monitoring suites, deploy Falco (from the CNCF) or Cilium Tetragon. Both hook directly into the Linux kernel via eBPF and can enforce strict, custom rulesets — including killing processes immediately upon detecting unauthorized syscalls, unexpected network activity, or file access outside permitted paths. Tetragon in particular supports enforcement at the kernel level (not just alerting), making it a genuine security boundary rather than just an observability tool.

**gVisor and Firecracker for strong software isolation.** These open-source tools (gVisor from Google, Firecracker from AWS) provide substantially stronger isolation boundaries than standard containers. gVisor interposes a user-space kernel that intercepts all syscalls, reducing the attack surface to the host kernel. Firecracker provides lightweight microVMs with a minimal virtual machine monitor. Neither provides the memory encryption guarantees of hardware TEEs — a physical attacker with access to the host's RAM could extract data. However, when combined with the safe-storage physical protocol described above, this gap is addressed: the hardware is physically inaccessible when not under direct observation. The combination of gVisor/Firecracker + safe storage achieves a threat mitigation profile comparable to enterprise TEE deployments for a fraction of the cost.

**Append-only audit logs on write-protected media.** Configure `syslog` or `journald` to write audit logs to a local storage medium with a hardware write-protect mechanism — an SD card with a physical write-protect switch, or a USB drive with a hardware write-protect toggle. Once the write-protect is engaged, the logs cannot be modified or deleted even by a process with root access on the host. This ensures that if an agent escapes the sandbox and gains elevated privileges, the forensic trail of the escape is preserved. This is a low-cost approximation of the append-only, tamper-resistant logging that enterprise environments achieve with dedicated WORM storage arrays.

### 11.4 Output Validation and Tool Brokerage

**The enterprise approach:** Dedicated validation servers, commercial API gateways, enterprise identity providers.

**Compensating controls:**

**Local policy-as-code with Open Policy Agent.** The orchestrator's tool brokerage and output validation can be enforced entirely via Open Policy Agent (OPA) running locally. The orchestrator evaluates the agent's tool intents against declarative Rego policies stored alongside the orchestrator code. No external identity provider or API gateway required. The policies are version-controlled and auditable — changes to what an agent is permitted to do are tracked in the same repository as the orchestrator itself.

**QR-code-based air-gap extraction.** For extracting small validated outputs (short text, cryptographic hashes, attestation proofs) from a Tier 0 air-gapped machine, QR codes provide a physics-enforced unidirectional data channel that avoids the attack surface of USB sneakernets entirely. The air-gapped machine encodes the validated output as a QR code displayed on its monitor. A separate, network-connected device scans the QR code via camera. This eliminates USB-based attack vectors (firmware-level attacks like BadUSB, autorun exploits, or malicious filesystem metadata) because no physical media is exchanged and the data flows through an optical channel with inherently limited bandwidth. This technique is well-established in cryptocurrency custody, secure key ceremonies, and high-assurance air-gapped systems. It is limited to small payloads (a few kilobytes per QR code, or more with a sequence of animated codes), so it complements rather than replaces USB sneakernet for large outputs like model checkpoints.

### 11.5 The Compensating Controls Principle

The common thread across all of these alternatives is that resource constraints do not require compromising on the *security properties* — they require achieving those properties through different mechanisms. A TPM is not an HSM, but it provides hardware-rooted key protection. A safe is not a mantrap, but it eliminates the physical access window. Falco is not a commercial SIEM, but it enforces the same kernel-level detection rules.

The compensating control must always be evaluated against the specific threat it addresses. If the primary control protects against Threat X, the compensating control must also protect against Threat X — not merely be a cheaper technology in the same general category. Security auditors evaluate compensating controls on this basis, and practitioners should as well.

---

## 12. Summary of Recommendations

**For organizations operating AI agents in production:**

- Implement at minimum Tier 1 containment (network namespace isolation, input/output validation) for any agent executing code or accessing tools
- Establish a trust tier classification process based on agent capability, data sensitivity, and behavioral evidence
- Build or adopt an orchestrator that enforces containment lifecycle, input sanitization, output validation, and audit logging
- Broker all tool access through the orchestrator — agents should not hold credentials directly
- Use ephemeral, scoped credentials for any agent tool access; no long-lived static API keys
- Treat agent memory stores (vector databases, conversation logs) as untrusted input
- Monitor agent behavior and build baselines for anomaly detection

**For organizations training frontier models:**

- Implement Tier 0 physical security for training infrastructure handling frontier model weights
- Hardware air gap adversarial research environments
- Evaluate confidential computing (NVIDIA H100 TEEs, AMD SEV-SNP) for protecting model weights in GPU and CPU memory
- Establish supply chain verification, hardware attestation, and tamper evidence programs
- Implement two-person integrity for physical access to training hardware and model weight storage
- Evaluate TEMPEST requirements based on threat model

**For organizations conducting adversarial AI research (sleeper agent testing, red-teaming):**

- Always use Tier 0 containment for adversarial evaluations
- Hardware air gap with sneakernet I/O and chain-of-custody logging
- Input validation and output validation on separate, purpose-built machines before any data crosses trust boundaries
- Cryptographic attestation of outputs for downstream chain-of-custody verification
- Full syscall tracing and behavioral monitoring during all adversarial execution
- Ephemeral execution environments created fresh from verified golden images for each task
- Physical security commensurate with the capability level of the models being tested

**For resource-constrained teams (academic labs, startups, independent researchers):**

- Achieve Tier 0 physical containment through dedicated air-gapped workstations with safe storage and tamper-evident seals (Section 11.2)
- Use TPM 2.0 for hardware-rooted disk encryption and measured boot in place of dedicated HSMs (Section 11.1)
- Deploy Falco or Tetragon for kernel-level runtime enforcement in place of commercial SIEM/monitoring (Section 11.3)
- Combine gVisor/Firecracker software isolation with physical safe storage to compensate for the absence of hardware TEEs (Section 11.3)
- Enforce synchronous execution discipline — Tier 0 runs only occur under direct researcher observation
- Use QR-code-based optical extraction for small outputs to avoid USB attack surface (Section 11.4)
- Apply compensating controls rigorously: each substitution must address the same threat as the primary control it replaces

---

## Appendix A: Technology Reference

| Technology | Purpose | Tier Applicability |
|---|---|---|
| Linux network namespaces (`ip netns`) | Kernel-level network isolation | Tier 1-2 |
| Seccomp-bpf | Syscall filtering | Tier 0-2 |
| Landlock LSM | Filesystem sandboxing | Tier 0-2 |
| Docker (`--network=none`) | Container isolation | Tier 1-2 |
| Firecracker microVM | Lightweight VM isolation | Tier 1-2 |
| gVisor | User-space kernel for system call interception | Tier 1-2 |
| nftables | Egress allowlist enforcement | Tier 2 |
| eBPF / bpftrace | Low-overhead system call tracing | Tier 0-2 |
| Hardware Security Module (HSM) | Key management for data-at-rest encryption and output signing | Tier 0-1 |
| TEMPEST shielding | Electromagnetic emanation control | Tier 0 |
| AMD SEV-SNP | VM-level memory encryption (CPU TEE) | Tier 0-2 (cloud) |
| Intel TDX | Trust domain memory isolation (CPU TEE) | Tier 0-2 (cloud) |
| NVIDIA Confidential Computing (H100+) | GPU memory encryption for model weights and activations | Tier 0-1 |
| AWS Nitro Enclaves | Isolated compute with cryptographic attestation | Tier 0-2 (AWS) |
| Azure Confidential VMs | SEV-SNP backed VMs with attestation | Tier 0-2 (Azure) |
| SPIFFE/SPIRE | Workload identity and ephemeral credential issuance | Tier 1-2 |
| HashiCorp Vault | Dynamic secrets and ephemeral credential management | Tier 1-2 |
| Open Policy Agent (OPA) | Policy-as-code for tool intent RBAC validation | Tier 1-2 |
| TPM 2.0 (Trusted Platform Module) | Hardware-rooted key sealing and measured boot (compensating control for HSM) | Tier 0-1 |
| FIDO2 / PIV hardware tokens | Hardware-bound signing keys for output attestation and HITL approval | Tier 0-2 |
| Falco / Cilium Tetragon | Open-source eBPF runtime security enforcement and detection | Tier 0-2 |

## Appendix B: Containment Checklist by Tier

### Tier 0 Checklist

- [ ] Dedicated physical hardware with no network interface
- [ ] No wireless radios (WiFi, Bluetooth) in hardware
- [ ] BIOS-level port restrictions (USB, Thunderbolt) where feasible
- [ ] Seccomp-bpf syscall filter applied
- [ ] Input sanitized and validated before injection into execution environment
- [ ] Input provided via write-blocked physical media
- [ ] Output extracted via dedicated media with chain-of-custody
- [ ] Output validated on separate machine before network contact
- [ ] Output cryptographically signed before transmission to downstream systems
- [ ] Full syscall tracing active during execution
- [ ] Execution environment created fresh per task from verified golden image
- [ ] Forensic snapshot captured before environment destruction
- [ ] Mantrap physical access with multi-factor authentication
- [ ] Two-person integrity rule enforced
- [ ] Tamper-evident seals on all chassis, verified on schedule
- [ ] Active surveillance monitoring during operations
- [ ] Honeypot systems deployed alongside production hardware
- [ ] NVIDIA Confidential Computing / AMD SEV-SNP enabled (if applicable hardware)

### Tier 1 Checklist

- [ ] Network namespace with no external interfaces
- [ ] Seccomp-bpf syscall filter applied (defense-in-depth)
- [ ] Container or microVM with resource limits (CPU, memory, disk, processes)
- [ ] TEE / confidential VM enabled for cloud deployments
- [ ] Execution environment created fresh per task from verified golden image
- [ ] Read-only input mounts
- [ ] Input sanitized: structural pre-processing, prompt injection scanning, schema validation
- [ ] Memory/vector store reads validated before injection
- [ ] Write restricted to designated output directory
- [ ] Agent process terminated before output extraction
- [ ] Output validated: schema, size, content scan
- [ ] Supervisor model review configured (if available)
- [ ] Output cryptographically signed before transmission
- [ ] Network reconnection only after validation passes
- [ ] Tool access brokered through orchestrator (no direct agent credentials)
- [ ] All credentials ephemeral with task-scoped TTL
- [ ] Forensic snapshot captured before environment destruction
- [ ] Process-level resource monitoring active
- [ ] Badge-access physical security with surveillance

### Tier 2 Checklist

- [ ] Container with egress allowlist (nftables or equivalent)
- [ ] DNS resolution through controlled resolver
- [ ] All network traffic logged
- [ ] Alerts configured for non-allowlisted egress attempts
- [ ] Input sanitized for external data sources (prompt injection scanning)
- [ ] Output schema validation (may be inline)
- [ ] Resource limits enforced
- [ ] Ephemeral, scoped credentials (SPIFFE/SPIRE, cloud IAM, or Vault)
- [ ] HITL approval gates for high-impact / irreversible actions
- [ ] Execution environment ephemeral (fresh per task)
- [ ] Behavioral baseline established and anomaly detection active
- [ ] Standard data center physical security

### Tier 3 Checklist

- [ ] Standard container or process isolation
- [ ] Organizational firewall policies applied
- [ ] Application-level logging
- [ ] Standard organizational physical security

---

*This framework is a living document. As AI agent capabilities evolve and new containment techniques are developed, the recommendations herein should be revisited and updated.*
