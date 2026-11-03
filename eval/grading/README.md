# Grading eval

Checks whether a local Ollama model can grade short learner Spanish well enough for the Level 1 assessment loop (`MVP_DESIGN.md` §8). It uses only the Python standard library, so no venv is needed.

```bash
python3 eval/grading/run_grading_eval.py --host http://<homelab>:11434 --model llama3.2 --runs 3
# compare models
python3 eval/grading/run_grading_eval.py --model llama3.2 --model qwen2.5:7b --runs 3
```

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
