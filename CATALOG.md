# Optimization Catalog

## Quick decision table

| Bottleneck / problem shape | First record to inspect | Core idea |
| --- | --- | --- |
| Deterministic tests/sweeps dominate runtime | [OPT-PY-001](optimizations/OPT-PY-001-deterministic-test-execution.md) | Reduce redundant/high-cost work while keeping coverage semantics |
| Same expensive result is recomputed at a proven-equivalent state | [OPT-INV-001](optimizations/OPT-INV-001-invariant-driven-reuse.md) | Prove equivalence, then reuse |
| Lean dependency reconstruction dominates CI | [OPT-LEAN-001](optimizations/OPT-LEAN-001-trust-preserving-lean-ci.md) | Verify reusable dependency state; rebuild current project source |
| Independent work can execute concurrently | [OPT-PAR-001](optimizations/OPT-PAR-001-bounded-parallel-execution.md) | Bound workers and prove scalar/parallel equivalence |
| Slow control state is inside a high-rate numerical/audio loop | [OPT-DSP-001](optimizations/OPT-DSP-001-control-rate-sparse-vector-dsp.md) | Separate rates, sparse-evaluate, vectorize |
| Inputs are unchanged but pipeline stages rerun | [OPT-INC-001](optimizations/OPT-INC-001-signature-bound-incremental-execution.md) | Bind work to complete input signatures and persist only successful state |
| Many simultaneous callers request identical not-yet-computed work | [OPT-COAL-001](optimizations/OPT-COAL-001-concurrent-duplicate-work-coalescing.md) | One in-flight computation, many waiters |
| Integer sets alternate between sparse and dense regions | [OPT-SET-001](optimizations/OPT-SET-001-density-adaptive-compact-sets.md) | Density-adaptive representation with exact set algebra |
| One global lock/counter/runtime domain serializes independent work | [OPT-CONT-001](optimizations/OPT-CONT-001-partitioned-coordination-domains.md) | Partition coordination while preserving the global invariant |
| Same deterministic transform is repeated for every consumer/replay | [OPT-FAN-001](optimizations/OPT-FAN-001-shared-materialization-fanout.md) | Materialize once, reuse many times |
| Expensive parameter evaluations are being guessed or exhaustively swept | [OPT-SEARCH-001](optimizations/OPT-SEARCH-001-budget-aware-adaptive-search.md) | Adaptive, budget-aware search over the declared problem contract |
| Exactness may be traded inside an explicit quality envelope | [OPT-APPROX-001](optimizations/OPT-APPROX-001-contract-bounded-approximation.md) | Bound the error/degradation and the resource cost together |
| Expensive stages consume candidates later discarded | [OPT-REDUCE-001](optimizations/OPT-REDUCE-001-early-working-set-reduction.md) | Reduce the working set before composition |
| Non-critical work delays the dependency chain users actually wait on | [OPT-CRIT-001](optimizations/OPT-CRIT-001-critical-path-prioritization.md) | Prioritize the critical path; speculate/defer deliberately |
| Small performance regressions accumulate unnoticed | [OPT-BUDGET-001](optimizations/OPT-BUDGET-001-performance-regression-budgets.md) | Guard stable performance expectations in CI |
| Discrete search space is huge but optimistic bounds are available | [OPT-PRUNE-001](optimizations/OPT-PRUNE-001-bound-driven-search-space-pruning.md) | Prune regions that provably cannot beat the incumbent |

Before selecting a record, define the target problem using [`OPTIMIZATION-PROBLEM.md`](OPTIMIZATION-PROBLEM.md).

## Frozen v1 records

### OPT-PY-001 — Deterministic test execution

**Status:** Verified mechanism; historical performance context incomplete.

QEC combined minimal fixtures, vectorized assertions, bounded deterministic caching, convergence/cycle early exit, smaller high-cost sweeps, lower safe iteration/trial counts, and repeated-work removal. Historical timings remain source observations, not transferable targets.

### OPT-INV-001 — Invariant-driven computation reuse

**Status:** Verified mechanism; historical performance context incomplete.

QEC encoded a baseline equivalence, tested exact equality and reused a proven-equivalent baseline result rather than rerunning the benchmark.

### OPT-LEAN-001 — Trust-preserving Lean CI

**Status:** Verified on source PR; timing observations are environment-scoped.

Separates source-state identity from compiled dependency artifacts, verifies reuse, rebuilds current project source, and keeps cold reconstruction claims separate.

### OPT-PAR-001 — Bounded parallel execution

**Status:** Verified, environment-specific.

Compares scalar and worker-count variants, checks output invariants and treats measured effective parallelism as evidence rather than assuming requested workers were used.

### OPT-DSP-001 — Control-rate sparse vector DSP

**Status:** Implemented reference for control-rate/sparse/vector patterns; approximation/native ideas partly proposed.

Precompute static state, evolve slow control state less often, evaluate sparse couplings and batch/vectorize hot numerical work.

The five records above are the immutable v1.0.0 formalized catalog. Their Lean model remains pinned; post-v1 records below do not silently alter it.

## Post-v1 records

### OPT-INC-001 — Signature-bound incremental execution
Persist complete effective-input identity after successful work and skip a stage only while that identity and required outputs remain valid.

### OPT-COAL-001 — Concurrent duplicate-work coalescing
Merge equivalent simultaneous misses into one in-flight computation instead of letting a thundering herd duplicate upstream work.

### OPT-SET-001 — Density-adaptive compact sets
Partition an integer domain and use sparse or bitmap-like containers according to local density while keeping exact set semantics.

### OPT-CONT-001 — Partitioned coordination domains
Replace one hot global coordination point with independently advancing domains while preserving required cross-domain invariants.

### OPT-FAN-001 — Shared materialization for fan-out and replay
Perform a deterministic transform once at the production boundary, persist/retain it when justified, and reuse it across consumers and replay.

### OPT-SEARCH-001 — Budget-aware adaptive parameter search
Classify the optimization problem, maintain a trial ledger, adapt future evaluations from observations, and stop under an explicit evaluation/resource budget.

### OPT-APPROX-001 — Contract-bounded approximation
Permit approximation only when the interface/scientific contract explicitly defines an error or degradation envelope and a reference path exists where practical.

### OPT-REDUCE-001 — Early working-set reduction
Push semantics-preserving filtering/culling/selection ahead of joins, rendering, simulation, DSP or other expensive composition.

### OPT-CRIT-001 — Critical-path prioritization
Prioritize work on the true latency dependency chain; prefetch/precompute likely-soon work only when justified; defer non-critical work.

### OPT-BUDGET-001 — Performance regression budgets
Protect a stable benchmark expectation with an environment-scoped, variance-aware CI budget rather than relying on remembered performance.

### OPT-PRUNE-001 — Bound-driven search-space pruning
Maintain a feasible incumbent, derive optimistic bounds for subregions, and discard regions that provably cannot improve the incumbent.

## Composition guidance

Optimizations compose only when their semantic and resource models compose.

- process parallelism plus BLAS/NumPy/native threads can oversubscribe CPUs;
- coalescing reduces duplicate identical work while adaptive search may instead need to diversify independent in-flight experiments;
- a compact representation may make a formerly remote problem feasible in memory, changing the architecture rather than merely reducing bytes;
- critical-path speculation can steal resources from the path it was intended to accelerate;
- approximation must never leak into an API whose callers still assume exact semantics;
- adaptive search can lose information efficiency when parallel batches are too wide;
- performance budgets require controlled environments or statistically defensible noise handling;
- pruning is valid only when the bound is sound.

Prefer one measured bottleneck removal at a time, then re-profile and reconsider the problem contract.
