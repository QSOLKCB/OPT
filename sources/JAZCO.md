# Source note — Jazco performance engineering articles

**Source index:** https://jazco.dev/

OPT uses these articles as mechanism donors and case studies. Reported production numbers remain source-reported historical observations unless independently reproduced in a target repository.

## Articles and extracted mechanisms

- `2023/09/28/request-coalescing/` — suppress concurrent duplicate work by sharing one in-flight result.
- `2024/04/20/roaring-bitmaps/` — density-adaptive integer-set representation and fast set algebra.
- `2025/09/26/interning/` — compact identity representation and partitioning of a global allocation hotspot into independent coordination domains.
- `2024/09/24/jetstream/` — compute/encode once, persist the reusable representation, fan out/replay without repeating transformation work.
- `2024/04/15/in-memory-graphs/` — representation compression can cross an architectural threshold and turn remote-query work into local set algebra.
- `2024/01/10/golang-and-epoll/` — vertical runtime coordination can become a bottleneck; partitioning processes/resources may outperform further vertical scaling; also illustrates explicit resource trade-offs.
- `2025/02/19/imperfection/` — bounded approximation under an explicit product/semantic contract.
- `2023/08/10/query-optimization/` — reduce a working set before expensive composition/join work.
- `2023/05/20/postgres-analyze/` — optimization quality depends on current workload/statistical models.

## Evidence boundary

OPT does not treat blog-case constants, machine sizes, throughput figures, thresholds or schema-specific choices as transferable. Target repositories must re-measure.

## Records informed

`OPT-COAL-001`, `OPT-SET-001`, `OPT-CONT-001`, `OPT-FAN-001`, `OPT-APPROX-001`, and `OPT-REDUCE-001`.
