# Monoraton Games — Play release privacy audit and public website

## Mission
Perform a defensible, evidence-based privacy/security and Google Play readiness audit of **lolZombies**, then publish a polished, accessible Monoraton Games website and an accurate lolZombies privacy policy. Work independently where safe; do not claim compliance without evidence.

## Known context
- Game repository: private `mrgarmise/lolzombies`, default branch `main`.
- Publisher GitHub organization: `monoratongames`.
- Website repository: public `monoratongames/monoratongames.github.io`; GitHub Pages already serves `https://monoratongames.github.io`.
- Public developer contact: `monoratongames@gmail.com`. Avoid publishing the developer's personal address, name, private credentials or personal GitHub username in the visible website.
- Current buildozer.spec observed: `package.name = lolzombies`, `package.domain = com.alexgames`, `version = 5.1.2`, `android.api = 36`, `android.release_artifact = aab`, `requirements = python3,kivy`.
- Google Play has accepted an uploaded AAB sufficiently to display version code `50102`; internal testing release is published and a tester has installed it. This does NOT prove policy compliance.
- GitHub Actions artifact seen in screenshot: `lolZombies-Play-AAB` (77.6 MB), plus `play-aab-build-log` and `play-aab-signature-verification`.
- User intends to use closed testing for production-access eligibility.

## Required investigation
1. Inspect the exact latest successful Play-targeted GitHub Actions workflow and retrieve its AAB and verification reports. Confirm commit SHA, build timestamp, version code/name, package/application ID, manifest permissions, target/min SDK, signing certificate fingerprints, build type, artifact provenance and whether the AAB matches the uploaded Play release where independently confirmable. If access or tooling prevents byte-level inspection, explicitly say so and provide reproducible commands rather than assuming.
2. Audit source, assets, buildozer.spec, Android manifest generation, CI workflows, packaged Python/native libraries and runtime behavior. Search for network requests, analytics/ads, crash reporting, identifiers, account systems, local saves, permission requests, credentials, URLs, logs, SDK collection and third-party code. Distinguish collection, on-device processing, transmission and sharing. Do not print secrets in reports; identify location and remediation securely. Check dependencies and licensing.
3. Consult current authoritative Google Play developer policies: User Data, Data Safety, privacy policy (public URL and in-app link/text), content rating, target API, app access, ads, families/target audience and other applicable declarations. Prepare a field-by-field suggested Data Safety answer sheet grounded in evidence, with uncertainties marked **requires confirmation**. Avoid categorical legal guarantees.
4. Check whether privacy policy is available within the game. If absent, propose a minimal in-app link implementation on a separate branch or PR, preserving existing gameplay and version/title-screen conventions. Do not silently publish a new game release, change the signing key, or alter the existing Play bundle.

## Website deliverables
5. Build a tasteful mobile-friendly, fast, accessible public homepage for Monoraton Games, with clear lolZombies listing and future-game-friendly structure. No analytics, cookies, trackers, remote fonts, or unnecessary JS. Do not falsely claim other games are released. Ensure the organization branding rather than personal branding appears in page metadata, footer, and links.
6. Publish a dedicated permanent privacy policy URL, preferably `https://monoratongames.github.io/lolzombies/privacy/`. Policy must name lolZombies, publisher and contact email; accurately explain data categories, processing, third-party services, retention/deletion, children/audience considerations, security, updates and contact as supported by the audit. Do not assert 'no data collected' until verified. Do not copy a generic policy with invented claims.
7. Publish website changes to the organization repo after testing locally; do not modify unrelated repositories. Confirm GitHub Pages deployment succeeds, homepage and policy return publicly without login, links work, mobile layout is usable, and the policy URL is stable. If deployment is unavailable, give precise blockers and a PR rather than claiming publication.

## Acceptance criteria and handoff
- Evidence table: each compliance claim, source/manifest/AAB finding, confidence, outstanding unknown and remediation.
- Artifact summary including hash(es), package ID, version, signing status, permissions and SDK details; clearly distinguish repo configuration from inspected binary facts.
- Public homepage and privacy policy links, verified live.
- Exact privacy-policy URL ready to paste into Play Console, only after publication and verification.
- Play Console declaration checklist, specifically Data Safety and privacy policy in-app requirement.
- Minimal prioritized blockers with next actions; no broad refactors or feature changes.
- Keep user informed of material findings, request approval before any sensitive, destructive or irreversible actions, and do not upload a replacement AAB or submit to Play Console without explicit approval.