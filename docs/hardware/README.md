# Hardware Documentation

Physical hardware systems for secure field deployment and agent terminal operation.

## Documentation

### [Secure Terminal Briefcase](./secure-terminal-briefcase.md)
Tamper-responsive Raspberry Pi briefcase with dual-sensor detection, cryptographic drive wipe, and quantum-safe recovery.
- Dual-sensor tamper detection (Hall effect + ambient light)
- Split-privilege systemd service architecture
- LUKS2 full-disk encryption with instant header destruction
- Hybrid classical/post-quantum key wrapping for recovery media
- **Implementation**: [`packages/tamper_briefcase/`](../../packages/tamper_briefcase/)

## Planned Systems

### Bluetooth Headset Integration
Paired audio device connected through the briefcase terminal. Disconnectable by voice command; reconnection requires physically opening the briefcase, disarming the wipe protocol, and re-pairing the audio device. Ensures the headset cannot be silently reassociated without triggering the tamper response chain.

## Related Documentation

- [Infrastructure](../infrastructure/) -- Software infrastructure (CI/CD, containers, runners)
- [Agent Security](../agents/security.md) -- Digital security model for AI agents
- [Wrapper Guard](../infrastructure/wrapper-guard.md) -- CLI binary tamper detection
