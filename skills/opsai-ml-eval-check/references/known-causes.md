# Known Causes — SageMaker-side evaluation (Nova recipe, LLM-as-judge) break-fix

Documented causes for the SageMaker-side evaluation problems operators report most (Nova evaluation
recipes and LLM-as-judge runs that execute as SageMaker training jobs), for answering a stated
symptom directly (SKILL.md, *Break-fix first*). Each bullet names the AWS page it rests on; verify
against that page before you answer. A cause tied to an `LLM-SM-EVAL-*` id is reported as that
finding with the catalog severity; a cause with no id is **guidance**, cited by URL, never given an
invented id. Where AWS says nothing (for example on benchmark data leaking from the fine-tuning
source), say so rather than filling the gap. A Bedrock `CreateEvaluationJob` (model or RAG) is
diagnosed on the Bedrock path (SKILL.md Step 3).

## 1. The evaluation job failed

- **Read the job's `FailureReason`, then the log group `/aws/sagemaker/TrainingJobs`** — AWS names that log group for Nova evaluation job errors (LLM-SM-EVAL-002) ([Nova evaluation troubleshooting](https://docs.aws.amazon.com/nova/latest/userguide/nova-model-evaluation.html)).
- **`RuntimeError: Engine core initialization failed`** typically means the checkpoint in `model_name_or_path` does not match `model_type` (for example a Nova 2.0 Lite checkpoint evaluated with a 1.0 model type) (LLM-SM-EVAL-002) ([Nova evaluation troubleshooting](https://docs.aws.amazon.com/nova/latest/userguide/nova-model-evaluation.html)).
- **Bring-your-own-dataset runs need exactly one file named `gen_qa.jsonl`**, in an S3 location the training job can read, with `query` and `response` on every line (`system`, `images`, `metadata` optional); only one `.jsonl` is allowed and it must follow the schema strictly (LLM-SM-EVAL-002) ([Nova evaluation](https://docs.aws.amazon.com/nova/latest/userguide/nova-model-evaluation.html)).
- **Access to the dataset and output paths is the job's execution role**: an evaluation runs as a training job, so the `CreateTrainingJob` execution role needs read on the input prefix, write on the output path and `kms:Decrypt` for SSE-KMS input (LLM-SM-EVAL-002) ([CreateTrainingJob execution role](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-roles.html)).

## 2. The job cannot start on an instance limit

- **`ResourceLimitExceeded` is an account resource limit** for the training instance the evaluation uses; request an increase through Service Quotas ([CreateTrainingJob errors](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_CreateTrainingJob.html), [quotas](https://docs.aws.amazon.com/sagemaker/latest/dg/regions-quotas.html)).

## 3. Scores swing between runs on the same model

- **Set `temperature: 0`** in the recipe's `inference` block; AWS states 0 makes results deterministic and larger values add randomness ([recipe parameters](https://docs.aws.amazon.com/nova/latest/userguide/customize-fine-tune-evaluate-understand-modify.html)).
- **Read the judge's own uncertainty before comparing runs**: `llm_judge` reports `*_stderr` for scores, ties and inference errors, plus `lower_rate` / `upper_rate` (2.5th / 97.5th percentile bootstrap bounds) on the Bradley-Terry `winrate`; treat a difference inside those bounds as noise, not a regression — this skill's reading ([recipe parameters](https://docs.aws.amazon.com/nova/latest/userguide/customize-fine-tune-evaluate-understand-modify.html); `upper_rate` is defined on [Nova evaluation](https://docs.aws.amazon.com/nova/latest/userguide/nova-model-evaluation.html)).

## 4. Scores from two model versions cannot be compared

- **Keep the results artifact, not the log lines**: the job writes a zip to the output S3 path with `eval_results/results_[timestamp].json` (metrics), per-task details and TensorBoard files; AWS's best practice is to keep output paths organized by model and benchmark with consistent naming, and the recipe's `mlflow_tracking_uri` / `mlflow_experiment_name` / `mlflow_run_name` fields log runs to MLflow (LLM-SM-EVAL-003) ([Nova evaluation](https://docs.aws.amazon.com/nova/latest/userguide/nova-model-evaluation.html)).

## 5. A domain metric no built-in covers

- **Use Bring-Your-Own-Metrics**: the `gen_qa` task supports a custom AWS Lambda for preprocessing and postprocessing that returns custom metrics, built with AWS's Nova custom evaluation layer ([Nova evaluation](https://docs.aws.amazon.com/nova/latest/userguide/nova-model-evaluation.html)).

## 6. "Did anyone evaluate this model?"

- **Look for an evaluation run as a training job against the artifact and for its results object** under the evaluation output path; AWS describes evaluation as a separate job pointing at the trained model that writes metrics to S3, so finding no such job or object means no SageMaker-side evaluation is on record — this skill's reading (LLM-SM-EVAL-001) ([Nova evaluation](https://docs.aws.amazon.com/nova/latest/userguide/nova-model-evaluation.html)).
