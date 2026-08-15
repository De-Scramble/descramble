# Security Policy

## Reporting a vulnerability

Please report security vulnerabilities privately to **security@descramble.dev**.

Do not open a public issue, pull request, or discussion for a suspected vulnerability. Public
disclosure before a fix exists puts every user of the project at risk.

A useful report includes:

- what the vulnerability is and the impact you believe it has,
- the version or commit you found it in,
- steps to reproduce it, ideally with a minimal example,
- any suggested remediation, if you have one in mind.

If you would like to encrypt your report, say so in a first message and we will arrange a key.

## What to expect, and when

De-Scramble is maintained by a small team. The commitments below are the ones we can actually
keep, which is the only kind worth publishing.

| Stage | Commitment |
|---|---|
| Acknowledgement of your report | **Within 7 days** |
| Assessment and triage | Promptly after acknowledgement, with our finding shared with you |
| Resolution | **Best effort, typically within 90 days** of acknowledgement |
| Public disclosure | Coordinated with you, normally once a fix is released |

The 7-day acknowledgement is a firm commitment. Resolution is best-effort: complex issues, or
issues rooted in an upstream dependency, can take longer than 90 days, and we would rather tell
you that plainly than publish a deadline we might miss. We will keep you updated on progress
rather than going silent, and we will tell you if a fix is going to take longer than expected.

We do not currently operate a paid bug-bounty programme. We will credit you in the release notes
and the changelog for the fix unless you would prefer to remain anonymous.

## Supported versions

De-Scramble is pre-1.0. Until a 1.0 release, security fixes are applied to the **latest release on
the default branch**, and we do not backport to earlier tags.

| Version | Supported |
|---|---|
| Latest release / default branch | Yes |
| Any earlier tag or release | No — please upgrade |

Once 1.0 ships, this table will be replaced by an explicit supported-version window.

## Scope

In scope: the De-Scramble source in this repository — the record-linkage pipeline, the lakehouse
writer, the input readers, the command-line interface, and the build and release workflows.

Out of scope: vulnerabilities in third-party dependencies (please report those upstream, and tell
us so we can pin or patch around them), and issues that require an attacker to already control the
machine running the pipeline.

Note that De-Scramble processes whatever records you point it at. Protecting the confidentiality of
your own input data, your warehouse, and your catalogue credentials is your responsibility; the
project ships no telemetry and transmits nothing anywhere.

## Steward

De-Scramble is operated and stewarded by **Deluge Limited**, which is responsible for handling
reports made under this policy.
