# Source note — Awesome WPO

- Repository: https://github.com/davidsonfellipe/awesome-wpo
- inspected identity: `84f32948a6298456d6a94cff64551f39f2666e6f`
- license: MIT

Awesome WPO is a curated web-performance index, not primary benchmark evidence. OPT uses it as a discovery source for two general mechanisms that extend beyond browsers:

1. **critical-path prioritization** — do latency-critical work now, speculate/prefetch likely-soon work when justified, lazily defer non-critical work, and avoid work with no demonstrated demand;
2. **performance budgets** — convert measured performance expectations into regression gates rather than relying on human memory of what "used to be fast".

Examples in the source catalog include lazy loaders, viewport-driven prefetching/resource hints, performance-budget tooling, browser timing APIs, Lighthouse/WebPageTest-style measurement, and real-user monitoring.

Any target-repository record must define its own metric, workload, environment, statistical tolerance and rollback rule. Browser-specific thresholds are not copied as universal constants.
