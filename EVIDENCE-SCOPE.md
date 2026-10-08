# Mathematical and formal evidence scope

Use this guidance when a new OPT record relies on a mathematical manuscript, a formal theorem or a replayable numerical certificate. Existing records and the pinned v1 model keep their established meanings; this guidance does not retroactively claim or require new formal proofs.

## Declare what is being established

| Evidence | What a successful check establishes | What it does not establish alone |
| --- | --- | --- |
| File hash / build-input manifest | The checked bytes match a recorded identity | The mathematics or implementation is correct |
| Numerical certificate replay | The replayed finite calculation passes its stated checks | Unchecked tensor constructions, analytic arguments or target runtime |
| Manuscript argument | A written derivation under stated hypotheses | Independent verification or faithful implementation |
| Lean theorem replay | The selected statement is proved under its definitions and allowed axioms | Every manuscript claim, external code equivalence or measured speed |
| Differential/conformance tests | The tested cases match the independent reference | Universal correctness beyond the tested domain |
| Target benchmark | The measured implementation behaves as recorded in that environment | Portable thresholds or an asymptotic theorem |

## Fields for new mathematical donors

Fill these fields in the optimization record's source/evidence section. Use an explicit scoped explanation when a field does not apply; do not leave a blank or silently infer coverage from a repository badge.

- **Computational model:** what operations cost, precision/bit-length assumptions, uniform versus nonuniform algorithms, charged preprocessing, memory definition and oracle assumptions.
- **Hypotheses / declared domain:** dimensions, graph class, input encoding, integrality, conditioning, supplied data and workload/adversary assumptions.
- **Guarantee and quantifiers:** all inputs or a subsequence; worst-case, expected or high-probability cost; one-/two-sided error; exact versus approximate output; decision versus witness construction.
- **Formal coverage:** main theorem, supporting lemma or no formalization; the exact correspondence and exclusions.
- **Proof target and toolchain:** fully qualified declarations, pinned solution files, compiler and dependency identities.
- **Axiom allowance:** actual permitted axioms and dependency boundary, including differences from OPT's trust model.
- **Certificate replay:** pinned payload/build inputs, exact commands and the mathematical assertions checked by each command.
- **Independent replay status:** who/what ran which command against which source identity, exit status and retained log; distinguish not attempted, failed and completed. Published instructions are not an executed replay.
- **Performance transfer:** separately identify target implementation, oracle validation, complete setup/replay costs, repeated environment-scoped measurements and remaining limitations.

## Formal challenge versus solution

OpenAI's [Comparator instructions](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/lean/ComparatorChallenges/README.md) route named challenge statements to separate solution modules. A `sorry` in a challenge specification is not the solution proof and must not be copied into OPT or treated as a completed proof. Check the configured solution, theorem/definition comparisons and permitted axioms through the advertised comparison procedure. Some comparisons cover supporting results only.

The donor uses Lean 4.34.1 and a substantial dependency graph. OPT's pinned v1 model uses Lean 4.33.1 and allows only `propext` in its full declaration audit. A donor comparison permitting `Classical.choice` or `Quot.sound` is a different trust boundary. Keep donor replay separate unless an explicitly reviewed, separately versioned integration satisfies OPT's existing gates. Never change the three pinned model files to make an external proof fit.

## Transfer examples

- An arithmetic-exponent bound does not establish practical crossover size, memory traffic or floating-point stability.
- An exact-complex DFT theorem does not establish a stable fast floating-point audio transform.
- A query-complexity bound with unrestricted intervening computation does not bound end-to-end tuning time.
- A three-machine unit-job scheduler does not cover arbitrary workers or unequal job durations.
- A randomized decision algorithm with false negatives cannot replace exact exhaustive search without an explicit contract change.
- A copied input manifest passes an integrity check only; execute the numerical replay separately before recording that calculation as checked.

See [the pinned donor assessment](sources/OPENAI-MATH.md) and [the record template](templates/OPTIMIZATION-RECORD.md). These examples guide evidence claims; they are not independent performance optimizations.
