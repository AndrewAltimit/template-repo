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
Practical framework for isolation, trust-tiered execution, and physical security for AI agent operations and frontier model training.
- Tiered trust model (Tier 0--3) mapping agent risk to proportional containment
- Network isolation via namespaces, containers, microVMs, and hardware air gaps
- Input/output validation pipelines with cryptographic attestation
- Physical security for frontier model training (facility access, TEMPEST, deception)
- Compensating controls for resource-constrained environments

| Document | PDF | Source |
|----------|-----|--------|
| AI Agent Containment & Infrastructure Security | [Download PDF](https://github.com/AndrewAltimit/template-repo/releases/latest) | [Markdown](./ai-agent-containment-infrastructure-security-framework.md) \| [LaTeX](./latex/ai-agent-containment-infrastructure-security-framework.tex) |
| BioForge CRISPR Automation | [Download PDF](https://github.com/AndrewAltimit/template-repo/releases/latest) | [Markdown](./bioforge-crispr-automation.md) \| [LaTeX](./latex/bioforge-crispr-automation.tex) |
| Secure Terminal Briefcase | [Download PDF](https://github.com/AndrewAltimit/template-repo/releases/latest) | [Markdown](./secure-terminal-briefcase.md) \| [LaTeX](./latex/secure-terminal-briefcase.tex) |

## Planned Systems

### Bluetooth Headset Integration
Paired audio device connected through the briefcase terminal. Disconnectable by voice command; reconnection requires physically opening the briefcase, disarming the wipe protocol, and re-pairing the audio device. Ensures the headset cannot be silently reassociated without triggering the tamper response chain.

## Related Documentation

- [Infrastructure](../infrastructure/) -- Software infrastructure (CI/CD, containers, runners)
- [Agent Security](../agents/security.md) -- Digital security model for AI agents
- [Wrapper Guard](../infrastructure/wrapper-guard.md) -- CLI binary tamper detection
