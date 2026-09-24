# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |

## Reporting a vulnerability

Please do **not** open a public issue for security vulnerabilities.

Report privately using GitHub's "Report a vulnerability" feature (Security
Advisory) on this repository. Include:

- affected version,
- a description of the issue,
- a minimal reproduction if possible,
- whether personal data or device control could be affected.

You will receive an acknowledgement as soon as possible. Please allow time for
a fix before public disclosure.

## Security model

PV Manager follows the principle of **fail-safe, not fail-proof**:

1. **Hard limits are deterministic.** No module, UI action or AI can bypass the
   central constraint engine.
2. **Unknown means stop.** Missing, stale, contradictory or unverified data
   blocks automation for the affected device.
3. **No guessed credentials.** API keys are stored in the Home Assistant config
   entry, are never returned through the websocket API and never logged.
4. **AI is advisory only.** The AI receives no tools and no service access.
5. **Privacy by default.** Local-only is the default. External AI requires an
   explicit privacy mode, an explicitly allowed provider and a confirmation.
6. **Bounded learning runs.** Calibration switches one device, with hard time,
   power, energy and grid-headroom limits, and turns it off on every exit path.
7. **No network scanning.** Device discovery uses existing Home Assistant entity
   and device registries, not unsolicited network probes.

## Deliberate limitations

- Software cannot verify electrical safety, fuses, cables or local regulations.
- A cloud provider may retain pseudonymized data according to its own policy.
- Pseudonymization reduces but does not eliminate re-identification risk.
- Home Assistant recorder data from original sensors remains under Home
  Assistant ownership and is not deleted by the PV Manager.
