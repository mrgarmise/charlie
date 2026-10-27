# Unified integration: reconciliation checkpoint

Source parents: PR #12 `ae09f52d1a1f65de2bcb923cb7d112d666fb5798`, including PR #11 `a19c90822687739f79f69587302006a1bd6364d4`; PR #10 `9c1319d2800749d19cd5086f34ba4643276d90a7`. Their common ancestor is `96e651373e513d24b4163b87c5f85bdd5549cf1d`. Original branches and their evidence remain intact.

The existing attention manager now handles both pet opportunity and object-label events. Mobile observation emits both events and calls the same attention manager; it uses the existing Executive lifecycle, independent mobile safety context, and shared camera subscription. The application owns the ELEGOO feeder during the hardware pet-follow entrypoint. The MJPEG reader retains the host-identity camera lease, while ordinary legacy camera clients subscribe. The legacy camera lease regression was migrated to exercise the actual reader rather than the public subscriber.

This is a software reconciliation checkpoint, not completed unified motion architecture or a native release. In particular, legacy face tracking still needs qualified actuator migration and witnessed parity; it must not be treated as qualified by this merge. Verified ultrasonic protocol, shared telemetry, a common RP2040 request gateway, exhaustive cross-process source ownership, and physical safety acceptance remain open. The object-recognition and pet application modes remain separate; simultaneous inference in one normal session has not been established. The pet-mode feeder is no proof of physical motion readiness. Existing independent qualification gates are not waived.

Test observations and failures are recorded with the PR. No hardware was accessed or moved. Do not deploy this checkpoint without the remaining architecture, native review and staged acceptance specified in the mission. Preserve existing Pi worktrees, firmware and evidence; rollback consists of stopping this uninstalled integration process and continuing to use the previously validated checkout, without resetting or replacing it.

## STOP uncertainty session latch

The qualified pet executor now latches an unconfirmed STOP or ambiguous pulse exception for the remainder of that executor session. A later STOP ACK does not clear the latch or permit a second start. This is a software defense, not proof of physical stopping, a persistent restart latch, or a replacement for a device-local watchdog/cutoff. The runtime hash changes, invalidating prior runtime-bound grants. Cross-restart requalification and unified legacy-face authority remain open.
