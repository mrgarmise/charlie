# Baselines and gates

| Dependency | Exact head | Tree | Verified GitHub status |
| --- | --- | --- | --- |
| [Discovery Engine #47](https://github.com/mrgarmise/charlie/pull/47) | `54ee8f8c9ece098e5ca93f348bb9ca8437115b20` | `53cfff4c310463e0088712eef350cd9f46e98e95` | Open draft. Discovery software, native-meditation software and consultation software passed at this head. |
| [Agent Factory #46](https://github.com/mrgarmise/charlie/pull/46) | `c648811bbc43585b0f37687af7074df31741dc35` | `1b33a75843dd731391f78a2467cf2fc747d3a8a9` | Open draft. Human questions, model learning, unified integration, Best of Charlie and Mobile Body workflows passed at this head. |
| Common ancestry and current observed master | `57e07eb850b139eda6a5f1a930cc0ef7b5bf5f18` | See Git | Includes runtime candidate source. |
| #47 stationary-review branch base | `5732d34f49db9b08ff8bb2f90c7eab10cfc0ae76` | `f58c8fc400ee3d78aff3178d264077b144ee8a29` | Includes the #36 and #38 development integration. |

This draft targets the #47 branch and applies the #46 delta from the common ancestor as an isolated commit. The combined pre-feature tree is `b2ba442f3898087fca929490074c66a7fa686113`. Other worktrees and the owner's Pi were outside this workspace. After #46 is integrated upstream, compare its effective tree with the pinned delta and drop the duplicate integration commit on a fresh review branch. Keep both parent drafts until reviewed.

The [Discovery handoff](../discovery/NATIVE_HANDOFF.md) reports private archive manifest SHA-256 `67a410118af9930b9b071eb264988ebd13c8643db683036ee222245ed2afa5d7`. Verifying the packet and private archive requires the original owner handoff bytes and the independently delivered outer digest. The public CODATA and IANA snapshots used by this sandbox were verified against the separately pinned repository data. The demonstration archive is its own development index.

The historical runtime commit/tree pair is `d3dca9059233b5f054c4f6f9979085b1422f9674` / `72cd9e4eba5939c181ae88d6ed03d5bbc50527c4`. Current approved and installed identities require a fresh Pi receipt. See the Discovery handoff for policy, controls, model and rollback checks.
