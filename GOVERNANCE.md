# Governance

## Who runs this project

De-Scramble is stewarded by **Deluge Limited**, which maintains the project, funds the work on it,
and is accountable for it. We say so plainly here, in the README, and anywhere the project collects
information, because you are entitled to know who is behind the software you are running.

Stewardship means responsibility for the project's health and direction. It does not mean ownership
of your contributions: the project is Apache-2.0, contributions are accepted under the Developer
Certificate of Origin, and there is no copyright assignment or Contributor Licence Agreement. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## The open-core promise

Deluge Limited earns from optional services — integration, hosting, support — and never from
withholding capability from the core. Concretely, and as a standing commitment:

- The core is **complete**. Features are not removed, degraded, or artificially limited in order to
  create demand for a paid tier.
- There is **no licence key**, no usage cap, no telemetry, and no phone-home.
- The licence stays **Apache-2.0**. The project is not relicensed to a source-available or
  non-compete licence.
- **Self-hosting is a first-class use.** Running De-Scramble yourself, forever, without paying
  anyone, is exactly what it is for. Nothing in our documentation will disparage that choice.

If you ever find these promises contradicted by the code, treat it as a bug and open an issue.

## How decisions get made

The project currently runs on a **benevolent-maintainer** model, which is an honest description of
its size rather than an aspiration to hierarchy.

1. **Proposals are public.** Anything beyond a small fix starts as an issue describing the problem
   before the solution.
2. **Discussion is in the open**, in that issue or the pull request. Design disagreements are
   settled on technical merit — correctness, clarity, and the cost of maintaining the result.
3. **Maintainers decide.** Where consensus does not emerge, a maintainer makes the call and records
   the reasoning in the thread, so the decision can be understood and revisited later.
4. **Some things are not up for negotiation:** the licence, the DCO-not-CLA model, the open-core
   promise above, and the requirement that the test suite stays green. A red suite blocks a merge.

## Becoming a maintainer

There is a real path, and it is the ordinary one:

1. **Contribute.** Land a handful of changes — code, tests, documentation, or well-triaged bug
   reports. Sustained, good-faith review of other people's pull requests counts for as much as
   writing your own.
2. **Take on an area.** Maintainers emerge from people who have picked up a part of the project and
   started caring about it: the linker, the lakehouse writer, the readers, the docs.
3. **Be invited.** An existing maintainer proposes you, publicly, in an issue. Existing maintainers
   agree.
4. **Get commit rights**, along with a say in the decisions above.

We would rather have a small number of engaged maintainers than a long list of inactive ones. If
you step away, that is fine and normal — tell us, and you can step back in later.

## Changing this document

Governance changes are proposed as a pull request against this file and left open long enough for
people to actually respond. Substantive changes are announced in the changelog.
