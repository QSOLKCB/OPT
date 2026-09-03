# OPT-INV-001 — Invariant-Driven Computation Reuse

**Status:** Verified mechanism; historical performance context incomplete  
**Domains:** tests, simulations, parameter sweeps, numerical kernels, build pipelines

## Source evidence

- https://github.com/QSOLKCB/QEC/releases/tag/v68.4.1
- https://github.com/QSOLKCB/QEC/commit/83f0479546e9d1d2bf8effdbbd2e18967c7ae711

## Core idea

The fastest expensive computation is the one you can prove you already performed.

QEC observed that the URW min-sum path at `rho = 1.0` is baseline-equivalent. Rather than execute a second benchmark for that grid point, the optimized test reuses the already-computed baseline result.

The hardening release then made the equivalence explicit with a named baseline constant/helper and direct equality validation, instead of leaving the optimization as an inline special case.

## Generic recipe

1. **State the equivalence** as a named invariant.
2. **Prove or regression-test it** at the strongest practical level: algebraic proof, bitwise equality, canonical receipt equality, or exact structured output equality.
3. **Centralize the predicate** that decides whether reuse is allowed.
4. **Compute the reference result once.**
5. **Reuse the exact result** at equivalent parameter/state points rather than reconstructing a lookalike.
6. **Keep the ordinary path** for non-equivalent points.
7. **Fail closed** if future changes invalidate the equivalence gate.

Pseudo-pattern:

```python
baseline = expensive_run(BASELINE_CONFIG)

for parameter in grid:
    if is_baseline_equivalent(parameter):
        result = baseline
    else:
        result = expensive_run(config_for(parameter))
    validate(result)
```

## Evidence

The QEC implementation commit reports roughly **43% speedup for the affected hot test** after eliminating one redundant `run_benchmark` call. The full suite remained green.

### Historical benchmark context

The cited implementation commit does **not** preserve enough benchmark metadata to make that 43% figure reproducible as a controlled benchmark:

- runner / OS / CPU model: **not recorded in the cited commit**;
- Python / NumPy / pytest versions: **not recorded**;
- baseline and optimized wall-clock values for the affected hot test: **not recorded**;
- repetitions / variance: **not recorded**.

The promoted fact is therefore the **verified equivalence-and-reuse mechanism**. The 43% figure is retained only as a source-reported historical observation. Any target repository must measure its own baseline and optimized timing before treating this pattern as a performance result.

## Why this is stronger than ordinary memoization

Memoization says, “the inputs look the same.” Invariant-driven reuse says, “these different-looking inputs are known to produce the same contract result.” That makes it applicable to parameter aliases, identity transforms, normalized representations and baseline-equivalent modes.

## Guardrails

- Never infer equivalence merely from similar metrics.
- Prefer exact equality where the invariant claims exact identity.
- Bind the reuse rule to all semantic inputs, not a single convenient parameter.
- If the implementation paths diverge in side effects, timing-sensitive behavior, randomness or hidden state, result reuse may be invalid even when mathematical outputs match.
- Keep a regression test whose sole job is to protect the equivalence.

## Rollback trigger

If the equivalence test fails, disable reuse immediately and execute the ordinary path until the invariant is re-established or versioned.
