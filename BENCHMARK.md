# Benchmark baseline

Regenerate with `./scripts/benchmark.sh` (add `BENCH_YOUTUBE=1` for the YouTube
leg) and compare against this table before releases. Wall time is submit → 100%
through the real API inside Docker. WER = word error rate vs the fixture's
reference text (lower is better). The `txtify-bench-cache` volume caches model
downloads: cold = first ever run per model, warm = subsequent runs
(inference only).

## 2026-07-16 — Docker Desktop macOS (arm64), CPU, 7.7GB RAM, 6s speech fixture

| run | cold | warm | text ok | WER | first transcribed line |
|-----|------|------|---------|-----|------------------------|
| whisper_tiny | 30s | 5s | yes | 7% | the quick brown fox jumps over the lazy dog. |
| whisper_base | 30s | 5s | yes | 7% | The quick brown fox jumps over the lazy dog. |
| whisper_small | 96s | 10s | yes | 7% | The quick brown fox jumps over the lazy dog. |
| whisper_medium | 298s | 26s | yes | 7% | The quick brown fox jumps over the lazy dog. |
| whisper_large | OOM | - | - | - | large-v3 (fp32, CPU) needs ~10GB+; container had 7.7GB |
| deepl en→el (base) | 10s | 10s | yes | - | Η γρήγορη καφέ αλεπού πηδάει πάνω από τον τεμπέλη σκύλο. |
| youtube (tiny) | 8s | 8s | yes | - | Alright so here we are one of the elephant's cool thing |

Notes:
- 7% WER = exactly 1 of 15 reference words wrong — the invented brand name
  "Txtify", which no ASR model knows. All models got every real word right on
  this clean TTS fixture; treat a jump in WER on the same fixture as a
  regression signal, not an absolute accuracy claim. (Published Whisper WER on
  clean English benchmarks: tiny ≈ 7-8%, base ≈ 5%, small ≈ 3.4%,
  medium ≈ 2.9%, large-v3 ≈ 1.8%.)
- Translation verified with a real DeepL API call (EN source → EL target),
  Greek asserted by character class in the SRT preview.
- YouTube leg downloads and transcribes a real 19s video inside the container
  (network-dependent; may hit YouTube bot checks on shared IPs).
- whisper_large needs more container memory than a default Docker Desktop
  allocation — raise Docker's memory limit to benchmark it.
