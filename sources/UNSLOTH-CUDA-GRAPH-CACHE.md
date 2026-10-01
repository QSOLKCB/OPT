# Source note — Unsloth CUDA graph cache regression

- Repository: https://github.com/unslothai/unsloth
- Issue: https://github.com/unslothai/unsloth/issues/12468
- Issue author: `floewe`
- Issue opened: 2026-10-01
- Evidence boundary: external issue report with reproducible before/after measurements and exact-source rebuild isolation; OPT does not copy donor code or promote donor constants as defaults.
- Licensing/provenance boundary: this note paraphrases publicly reported measurements and experimental conclusions only. Any code reuse must follow the source repository's applicable license independently.

## Why this source matters

Issue #12468 reports a decode-performance regression in Unsloth's mixed llama.cpp builds when using multi-GPU `--split-mode tensor`. The reporter compared good and regressed builds across native Windows, WSL2 and bare-metal Linux, while also checking single-GPU and layer-split paths.

The reported evidence isolates CUDA graph cache capacity as the relevant variable:

- the earlier good build with CUDA graphs explicitly disabled falls to the same performance/VRAM regime as the regressed build;
- the regressed build does not materially change when graphs are disabled, consistent with graph reuse already having collapsed;
- rebuilding the exact release source reproduces the regression;
- reverting the changed graph key does not restore performance;
- changing only `static const size_t max_cuda_graphs = 64;` to a deliberately very large diagnostic value restores the fast regime in the reporter's WSL2 reproduction.

In the source report, the exact-source WSL2 test moved from roughly 32–33 tokens/s with the released cap to roughly 94–101 tokens/s with the diagnostic large cap. The reporter explicitly states that the huge replacement value is a test, not a proposed production fix.

The issue also reports a 36 MiB-per-GPU VRAM difference between the graph-reusing and regressed prebuilt regimes, plus smaller but still observable regressions on bare-metal Linux. Single-GPU and layer-split paths remain unaffected in the described tests.

## OPT interpretation

The transferable mechanism is not "increase 64." It is:

> A reuse cache must be sized and managed against the active reuse working set and memory/resource budget. If useful states are evicted before their next reuse, the cache can convert intended reuse into repeated reconstruction/recapture work.

The source therefore motivates `OPT-CACHE-001`: measure or derive effective working-set cardinality and reuse distance, then choose capacity/admission/eviction policy under an explicit resource budget. Fixed capacities are source-environment parameters until re-measured.

## Limits

- The evidence is scoped to the reporter's stated hardware, builds, models and commands.
- Windows/WSL2 showed a much larger slowdown than bare-metal Linux, so effect size is environment-specific.
- The issue demonstrates the failure mode and an isolation experiment; it does not establish a universal optimal cache size or a merged generic fix.
- A target adopting this pattern must validate correctness, memory growth, hit/eviction behavior and end-to-end performance locally.
