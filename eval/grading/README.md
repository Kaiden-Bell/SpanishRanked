# Grading eval

Checks whether a local Ollama model can grade short learner Spanish well enough for the Level 1 assessment loop (`MVP_DESIGN.md` §8). It uses only the Python standard library, so no venv is needed.

```bash
python3 eval/grading/run_grading_eval.py --host http://<homelab>:11434 --model llama3.2 --runs 3
# compare models
python3 eval/grading/run_grading_eval.py --model llama3.2 --model qwen2.5:7b --runs 3
```

## Grading through the application's own code

`--backend` runs the same cases through `src/backend/app/assessment/grade.py` and the real Ollama and LanguageTool clients (same prompts, validation and one retry on invalid output), so the numbers describe what the app does. It needs the project's virtualenv because the backend uses `httpx`:

```bash
.venv/bin/python eval/grading/run_grading_eval.py --backend --model qwen2.5:7b --runs 3
```

It adds a "Needed a retry" line to the summary. Two cautions when reading the latency: Ollama reuses its prompt cache for repeated identical prompts, so `--runs 3` makes runs 2 and 3 look faster than a learner will see (compare run 0); and a busy host inflates every number, so run it when nothing else is using Ollama. The scoring counts MISS where PARTIAL was expected as wrong, but both pay zero XP in the app, so also check wrongly-paid answers (a wrong answer marked HIT), which is the failure that matters for XP.

`cases.json` pairs each learner error with a correct control sentence, and adds two adversarial cases (prompt injection, and a target concept that never appears). `expected` lists the acceptable outcomes for each concept.

## Reading the summary

| Metric | Meaning | Suggested bar |
| --- | --- | --- |
| Error detection | Real errors marked PARTIAL/MISS | ≥ 80% |
| False-error rate | Correct usage marked wrong; the most harmful failure | ≤ 10% |
| Adversarial pass | Injection ignored, missing concept marked MISS | 100% |
| Schema validity | Output passed backend-style validation | ≥ 95% |
| Consistency | Same outcomes across `--runs` | high |
| Latency p95 | Seconds per graded answer | ≤ 15 s |

Raw responses, including feedback text, are written to `eval/grading/results/`, which is gitignored. Read the feedback text too: a model can get the outcome right and still give a wrong explanation.
