# STAGE 0b — CREDENTIAL CUSTODY CLEANUP — 2026-07-23 (UTC)

Operator: Nathan (CEO) · Verifier: Phase-1 Run session · Risk: R1 · **Result: PARTIAL — operational custody established; password-manager attestation pending** (CEO-directed status, 2026-07-24)

| Item | Value |
|---|---|
| Old path | ~/Downloads/ssh-key-2026-06-30.key |
| New path | ~/.ssh/seatwatch-vm.key (mode 600; ~/.ssh mode 700) |
| Downloads state | DOWNLOADS-CLEAR |
| Fingerprint pre/post | SHA256:9N+IY+uXnFq/wrGpYL0+ezUY0QZqePy5skJcsqDJcuU — match: yes |
| Access verification | ACCESS-OK on seatwatch, with IdentitiesOnly=yes |
| Key contents displayed | Never |
| Production | Not modified |
| Canonical path going forward | `~/.ssh/seatwatch-vm.key` (Stage 2 deploy tooling will reference this) |

**Open item (attestation pending):** the Q2 second copy — password manager name + item name — was not included in the evidence. The acceptance criterion "secure second copy exists BEFORE the move" is unconfirmed in the record. CEO to attest in one line (manager + item name); if the copy was not made, it should be made now from `~/.ssh/seatwatch-vm.key` via Finder (`open "$HOME/.ssh"`), never via terminal display.

**Not reported (minor):** Q1 recon findings (any `.pub` or duplicate key copies in Downloads, ssh-config line count) were not pasted — assumed none; flag if otherwise.
