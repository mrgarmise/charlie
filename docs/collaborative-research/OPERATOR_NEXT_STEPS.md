# Operator next steps

1. **Try on a workstation.** In a clean checkout of this draft head, use an owner-only working directory and Python 3 with the repository requirements and SQLite FTS5. Run:
   ```sh
   demo_dir=$(mktemp -d)
   python3 -B -m tools.discovery_collaborative_demo "$demo_dir" > "$demo_dir.json"
   python3 -B -m tools.discovery --journal "$demo_dir/research.sqlite3" ask \
     'What did the Researcher find?' --session-id retained
   ```
   Expected sequence: broad/inconclusive, scoped/reconciled, broad/inconclusive with frozen memory, then timing/reconciled. Report JSON gives source IDs, comparisons, work consumed and measured resource use. Save the directory and report if needed. Stop the foreground process with Ctrl-C and preserve its directory for inspection. No Pi access is needed.
2. **Inspect or recover a foreground sandbox session.** Start one with `python3 -B -m tools.discovery_collaborative --sandbox "$demo_dir" run manual --question study-1`. From the same workstation and checkout, use `pause manual` or `cancel manual` in place of `run manual --question study-1`. Use `resume manual` to continue a paused or interrupted attempt within the original deadline. Use `inspect manual` to read the Discovery record. `run manual` again reconciles an already-cancelled Factory with its Discovery session if the original foreground runner was interrupted. A lease interrupted by a hard kill may take up to 30 seconds to expire. Abort on archive identity drift or persistent admission failure and retain the whole sandbox as evidence.
3. **Recover the original #47 packet.** On the workstation that received the owner handoff, make the complete original release packet and its independently delivered outer SHA-256 available in the next Work run. From the extracted packet directory run `sha256sum -c SHA256SUMS`. Compare `RELEASE.json` and the private archive hash to [the pinned baseline](BASELINES_AND_GATES.md). Stop on any mismatch or missing file.
4. **Run Discovery G0 read-only on Charlie.** Use the verified #47 candidate bundle in an isolated checkout, the existing `~/charlie-ops` and the actual SSD mount. Follow [the exact G0 preflight, audit and receipt procedure](../discovery/NATIVE_HANDOFF.md). Capture current runtime commit and tree, active launcher and service/control hashes versus the independent ops snapshot, boot ID, scheduler policy/socket ownership and permissions, cgroups, memory, thermal/cooldown state, SSD headroom, lease inventory, and the model blob digest. Stop on drift. The packet and these receipts permit the existing native mission to resume at G0. A later paired foreground Qwen comparison requires a separately confirmed independent grant and operator at the Pi.
5. **Review and authorize any promotion separately.** Integrate the #46 and #47 dependency sources under explicit merge approval and drop any duplicated integrated delta from the review branch. Native qualification, foreground trial, deploy/rollback, live network grants and recurring research each need their own authorization. Preserve prior runtime evidence and all motion restrictions.

The next Work instruction after the original packet is accessible is:

> Resume the Charlie Civilization Discovery Native Qualification mission at read-only G0 for PR #47 head `54ee8f8c9ece098e5ca93f348bb9ca8437115b20`. Verify the original packet and fresh Pi control receipts. Stop before any live pilot, activation, service change or motion.
