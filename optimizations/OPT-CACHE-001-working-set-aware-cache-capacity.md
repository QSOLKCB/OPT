# OPT-CACHE-001 — Working-set-aware cache capacity

**Status:** Proposed / OPT synthesis; Unsloth issue #12468 provides controlled external evidence for the failure mode, not a universal cache-size prescription.  
**Domains:** GPU runtimes, graph caches, compiled-kernel caches, memoization, CI/build caches, services, inference systems

## Source evidence

- Repository: `unslothai/unsloth`
- Issue: https://github.com/unslothai/unsloth/issues/12468
- Issue opened: 2026-10-01
- Source note: `sources/UNSLOTH-CUDA-GRAPH-CACHE.md`
- Evidence boundary: the external report isolates a cache-capacity regression with exact-source rebuilds and controlled variants; OPT generalizes the mechanism without promoting `64`, `1048576`, or any donor-specific capacity as a target default.
- Licensing/provenance boundary: this record paraphrases public measurements and the reported experimental conclusion. Any donor code reuse must be licensed independently.

## Problem

A bounded reuse cache can become slower than the intended reuse path when the number of distinct states needed within the reuse horizon exceeds effective cache capacity. Useful entries are evicted before they are reused, so the system repeatedly reconstructs, recompiles, recaptures, reloads, or recomputes work that the cache was meant to avoid.

This failure can be deceptive because the cache still exists, correctness may remain intact, and memory use may even decrease while latency or throughput collapses.

## Optimization problem contract

- X: cache-capacity, admission, retention, eviction and partitioning policies for a declared reusable-state key space and workload/topology, including any bounded dynamic-sizing policy.
- F: policies that preserve exact externally visible semantics, maintain unambiguous cache-key identity, remain inside the declared memory/resource budget, avoid stale-state reuse, and are evaluated against the target workload's observed reuse working set rather than an imported donor constant.
- f: target-measured total cost comprising cache-hit execution, miss/reconstruction cost, eviction/re-admission cost, lookup/metadata overhead, memory footprint and any initialization or synchronization overhead paid by the workload.
- d: minimize total workload cost subject to the correctness and resource constraints; where memory and latency/throughput trade off, use the target's predeclared weighted, Pareto or lexicographic order rather than silently maximizing hit rate.
- C: no incorrect aliasing between semantically distinct states, no stale reuse beyond the target validity contract, no unbounded memory growth disguised as optimization, and no performance claim based only on cache hit rate without end-to-end measurement.
- B: target-specific measurement and tuning budget covering representative reuse-distance/cardinality observation, candidate capacity/policy trials, memory accounting and repeated end-to-end validation.
- S: stop when a policy satisfies the declared resource envelope and further capacity/policy changes do not produce material end-to-end benefit under the target's predeclared margin, or when the tuning budget is exhausted; retain/revert to the reference policy otherwise.
- Variables: integer, categorical, conditional and mixed
- Search scope: local
- Objective behavior: deterministic or noisy depending on workload/runtime
- Information: derivative-free
- Evaluation cost: moderate to expensive
- Constraints: semantic and resource
- Parallelism: sequential or synchronous batch; parallel trials only when interference is characterized
- Exactness: exact

## Preserved contract

Cache policy may change which reusable state is retained and when reconstruction occurs, but it must not change the externally declared result.

Cache keys must distinguish every state dimension required for correctness. Increasing capacity must never be used to mask an incorrect key. Decreasing capacity must not alter semantics merely because reconstruction becomes more frequent.

Memory/resource limits are part of the contract. An unbounded cache that prevents eviction thrash by exhausting VRAM, RAM, file descriptors, disk, or another constrained resource is not a valid implementation of this pattern.

## Optimization

Treat cache capacity as a function of the **active reuse working set**, not as a universal magic number.

For a reuse horizon `H`, define or estimate:

- `W(H)`: the number of distinct valid cache states whose next reuse occurs within `H`;
- reuse distance / stack distance for those states where practical;
- reconstruction cost per miss;
- retained-state memory/resource cost;
- eviction frequency and premature-eviction rate;
- end-to-end hit/miss consequences rather than hit rate alone.

A fixed-capacity cache of size `K` is at risk when useful `W(H)` materially exceeds `K` and entries are evicted before their next reuse. Depending on the target, valid remedies can include:

1. increase capacity only as far as the measured resource budget permits;
2. derive capacity from workload/topology dimensions that determine reusable-state cardinality;
3. partition the cache so unrelated state classes do not evict one another;
4. change admission/retention/eviction policy to protect expensive or soon-reused states;
5. reduce unnecessary key cardinality only when the merged states are proven semantically equivalent;
6. shrink individual retained states so more useful entries fit within the same resource envelope;
7. bypass or disable caching for state classes where retention overhead exceeds reuse benefit.

The optimization target is **minimum total workload cost under a bounded resource envelope**, not maximum cache size and not maximum raw hit rate.

## Before / after evidence

- Environment: external donor evidence spans native Windows, WSL2 and bare-metal Linux on multi-GPU RTX 5070 Ti systems; effect size differs materially by environment.
- Workload/fixture: Unsloth/llama.cpp tensor-split decode with repeated CUDA graph states; the issue also compares layer split and single-GPU controls.
- Cold baseline: the external issue's exact released source reproduces the regressed regime in WSL2 at roughly 32–33 tokens/s.
- Warm/no-op baseline where relevant: the earlier good build with CUDA graphs enabled operates in a much faster regime; explicitly disabling graphs makes that build fall to the same slow/low-VRAM regime as the affected build.
- Small invalidation / partial-work case where relevant: not separately characterized in the source report.
- Large invalidation / full-work case where relevant: the exact-source tensor-split workload repeatedly exceeds the released cache's useful retention regime.
- Optimized: the reporter changed only `max_cuda_graphs = 64` to a deliberately huge diagnostic value and observed roughly 94–101 tokens/s in the same WSL2 source build.
- Speedup / memory / I/O / quality change: the diagnostic capacity change restored the fast graph-reuse regime in that reproduction, while also increasing retained VRAM. The donor's huge replacement value is evidence that capacity was causal, not a recommended target setting.
- Variance / repetitions / raw samples: issue #12468 includes repeated short-generation samples, long-prompt cases, multiple builds and cross-platform controls. See the source issue for the raw tables.

## Validation

A target implementation should:

- record cache lookups, hits, misses, insertions, evictions and reconstruction/recapture events;
- distinguish capacity misses from compulsory/cold misses where practical;
- measure useful-state cardinality and reuse distance on representative workload phases;
- retain an uncached or known-correct reconstruction path as the semantic reference;
- verify that cached and reconstructed results are equivalent under the target exactness contract;
- test that deliberately small capacities reproduce expected miss/eviction pressure rather than silently changing semantics;
- test that increasing capacity reduces premature reconstruction only when the working set justifies it;
- account for the memory/resource cost of retained states;
- test workload/topology changes that alter key cardinality;
- verify that key changes and capacity changes are isolated experimentally when diagnosing a regression;
- measure end-to-end latency/throughput and resource use, not only hit rate.

When possible, include a known-thrash fixture whose active reuse working set exceeds a deliberately small capacity and a known-fit fixture whose active set fits comfortably. The gate should detect the transition without requiring a universal threshold.

## Target-repo adaptation

Re-profile cache-state cardinality, state size, reuse distance, miss/reconstruction cost, memory budget, concurrency, topology, shape/model dimensions, partitioning and eviction policy.

Do not copy the donor's `64` cap, the diagnostic `1048576` value, its GPU count, model, context length, split mode, VRAM observations or performance ratios as target defaults.

If capacity is derived dynamically, bind it to explicit measurable dimensions and clamp it to the declared resource envelope. If admission or key cardinality is changed, prove semantic equivalence separately from the capacity experiment.

## Failure modes

- A fixed cap is below the useful reuse working set and causes repeated eviction/reconstruction thrash.
- An oversized cache removes thrash but exceeds VRAM/RAM/disk or creates paging/allocator pressure that is worse overall.
- A supposedly equivalent key merge aliases states that are not semantically interchangeable.
- A high hit rate hides expensive misses on the critical path.
- Global LRU or similar policy lets one state class evict another class with higher reconstruction cost or shorter reuse distance.
- Workload phases or topology change after tuning and invalidate the chosen capacity.
- Concurrent producers inflate transient cardinality beyond the measured single-thread/single-request working set.
- Cache metadata, locking or lookup cost dominates when retained computations are cheap.
- A capacity increase appears beneficial only because benchmark warm-up or retained state leaks across trials.
- The target confuses lower memory use with better performance when the saved memory came from losing useful retained state.

## Rollback trigger

Revert or reduce the cache policy when retained-state memory/resource use exceeds the declared envelope, correctness/conformance fails, workload drift makes the tuned policy unstable, or total end-to-end cost no longer improves over the reference policy by the target's predeclared material margin.

If eviction/reconstruction counters rise sharply after a workload/topology change, treat that as a recalibration trigger rather than automatically raising the cap. If a larger cap merely transfers the bottleneck to memory pressure, allocation, synchronization or lookup overhead, revert and re-profile.

## Composition notes

This pattern composes naturally with:

- `OPT-INV-001` when state equivalence can safely reduce key cardinality or enable reuse;
- `OPT-BUDGET-001` to detect performance regressions caused by cache-thrash reintroduction;
- `OPT-AUTO-001` when several exact cache policies are calibrated and selected under a common cost/memory boundary;
- `OPT-CONT-001` when one global cache/lock should be partitioned without breaking global invariants;
- `OPT-REDUCE-001` when retained-state size or candidate cardinality can be reduced before caching.

Re-measure interactions carefully: partitioning can reduce contention but also lower effective capacity per partition; parallelism can increase simultaneous working-set cardinality; and invariant-driven key merging is valid only when equivalence is proved rather than inferred from performance.
