# Threat model

Treat proposals as untrusted data. A proposal has no transport access. A valid simulation command must satisfy the independently configured profile and live session bounds before the adapter runs. A physical connector always raises DENIED_PHYSICAL_AUTHORITY. The research runner has no hardware transports or imports from Charlie's runtime.

Python adapters are trusted code. The research package is not an isolation boundary for an arbitrary Python plug-in. Digests detect accidental payload corruption. An attacker with write access to the database can replace both payload and digest. The lease is checked around simulator calls and cannot interrupt a blocked native call. This package cannot issue hardware qualification.
