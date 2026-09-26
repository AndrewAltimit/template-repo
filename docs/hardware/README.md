# Hardware Documentation

Physical hardware systems for secure field deployment, agent terminal operation, and biological automation.

## Documentation

### [Secure Terminal Briefcase](./secure-terminal-briefcase.md)
Tamper-responsive Raspberry Pi briefcase with dual-sensor detection, cryptographic drive wipe, and quantum-safe recovery.
- Dual-sensor tamper detection (Hall effect + ambient light)
- Split-privilege systemd service architecture
- LUKS2 full-disk encryption with instant header destruction
- Hybrid classical/post-quantum key wrapping for recovery media
- **Implementation**: [`packages/tamper_briefcase/`](../../packages/tamper_briefcase/)

### [BioForge CRISPR Automation](./bioforge-crispr-automation.md)
Agent-driven biological automation platform with Raspberry Pi 5, closed-loop experiment orchestration, and defense-in-depth safety architecture.
- Raspberry Pi 5 with ESP32 co-processor for real-time control
- MCP tool endpoints for liquid handling, thermal control, and imaging
- Protocol state machine with human-in-the-loop gates
- Multi-layer safety interlocks with immutable audit logging
- **Implementation**: [`packages/bioforge/`](../../packages/bioforge/)

### [AI Agent Containment & Infrastructure Security](./ai-agent-containment-infrastructure-security-framework.md)
Practical framework for isolation, trust-tiered execution, and physical security for AI agent operations and frontier model training (v2.0, September 2026).
- Tiered trust model (Tier 0-3) with lethal-trifecta and agent-chain modifiers and a tier assignment decision flow
- Isolation: sandbox backend comparison (gVisor, Kata, Firecracker, WASM), seccomp and Landlock, egress-proxy allowlisting, and confidential-computing limits after TEE.fail and DDRop
- Agent-specific controls: orchestrator tool brokerage, MCP/tool supply chain pinning, architectural prompt-injection defenses, multi-agent controls
- 2025-2026 threat model: swarm and orchestrated agent campaigns, evaluation awareness, incident table mapped to OWASP Agentic Top 10 and MITRE ATLAS
- Operations: containment-probing detection, graduated K1-K5 kill switch with rollback, breakout incident response playbook
- Physical and weight security mapped to RAND SL1-SL5, plus compensating controls for resource-constrained environments

### [Agent Swarm Honeypot Guide](./agent-swarm-honeypot-guide.md)
Program guide for using deception to detect, attribute, and report misaligned autonomous AI agent swarms.
- Five design principles: detection on touch, uniqueness per placement, secrecy of keys not method, zero legitimate use, provider-actionable evidence
- Threat model of agent swarms versus human operators and classic bots, with adversary tiers A-D
- Five deception layers, from perimeter sensors to downstream indicators, designed from your own environment rather than public templates
- Correlating cautious, proxied adversaries through token reuse graphs and behavioral fingerprints
- Provider reporting package, community sharing, legal and ethical guardrails, and a four-level maturity model
- Companion to the containment framework above

| Document | PDF | Source |
|----------|-----|--------|
| AI Agent Containment & Infrastructure Security | [Download PDF](https://github.com/AndrewAltimit/template-repo/releases/latest) | [Markdown](./ai-agent-containment-infrastructure-security-framework.md) \| [LaTeX](./latex/ai-agent-containment-infrastructure-security-framework.tex) |
| Agent Swarm Honeypot Guide | [Download PDF](https://github.com/AndrewAltimit/template-repo/releases/latest) | [Markdown](./agent-swarm-honeypot-guide.md) \| [LaTeX](./latex/agent-swarm-honeypot-guide.tex) |
| BioForge CRISPR Automation | [Download PDF](https://github.com/AndrewAltimit/template-repo/releases/latest) | [Markdown](./bioforge-crispr-automation.md) \| [LaTeX](./latex/bioforge-crispr-automation.tex) |
| Secure Terminal Briefcase | [Download PDF](https://github.com/AndrewAltimit/template-repo/releases/latest) | [Markdown](./secure-terminal-briefcase.md) \| [LaTeX](./latex/secure-terminal-briefcase.tex) |

## Planned Systems

### Bluetooth Headset Integration
Paired audio device connected through the briefcase terminal. Disconnectable by voice command; reconnection requires physically opening the briefcase, disarming the wipe protocol, and re-pairing the audio device. Ensures the headset cannot be silently reassociated without triggering the tamper response chain.

## Related Documentation

- [Infrastructure](../infrastructure/): Software infrastructure (CI/CD, containers, runners)
- [Agent Security](../agents/security.md): Digital security model for AI agents
- [Wrapper Guard](../infrastructure/wrapper-guard.md): CLI binary tamper detection
