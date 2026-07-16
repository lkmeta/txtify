# Benchmark baseline

Regenerate with `./scripts/benchmark.sh` (add `BENCH_YOUTUBE=1` for the YouTube
leg) and compare against this table before releases. Wall time is submit → 100%
through the real API inside Docker; **first run per model includes the model
download** — the `txtify-bench-cache` volume makes later runs inference-only.

## 2026-07-16 — Docker Desktop macOS (arm64), CPU, 7.7GB RAM, 6s speech fixture

| run | wall time | text ok | first transcribed line |
|-----|-----------|---------|------------------------|
| whisper_tiny | 30s | yes | the quick brown fox jumps over the lazy dog. |
| whisper_base | 30s | yes | The quick brown fox jumps over the lazy dog. |
| whisper_small | 96s | yes | The quick brown fox jumps over the lazy dog. |
| whisper_medium | 298s | yes | The quick brown fox jumps over the lazy dog. |
| whisper_large | FAILED | - | out of memory: large-v3 (fp32 on CPU) needs ~10GB+; container had 7.7GB |
| deepl en→el (base) | 10s | yes | Η γρήγορη καφέ αλεπού πηδάει πάνω από τον τεμπέλη σκύλο. |
| youtube (tiny) | 8s | yes | Alright so here we are one of the elephant's cool thing |

Notes:
- Translation verified with a real DeepL API call (EN source → EL target),
  Greek asserted by character class in the SRT preview.
- YouTube leg downloads and transcribes a real 19s video inside the container
  (network-dependent; may hit YouTube bot checks on shared IPs).
- whisper_large needs more container memory than a default Docker Desktop
  allocation — raise Docker's memory limit to benchmark it.
