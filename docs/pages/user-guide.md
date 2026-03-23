# User Guide

This guide covers configuration, CLI commands, and advanced features of Kedro Azure ML.

## Configuration reference

All settings live in `conf/<env>/azureml.yml`. The top-level structure is defined by `KedroAzureMLConfig`:

```yaml
workspace:    # required, named Azure ML workspace definitions
compute:      # required, named compute cluster definitions
execution:    # optional, environment and code upload settings
schedules:    # optional, reusable schedule definitions
jobs:         # optional, named job definitions
```

### Workspaces

```yaml
workspace:
  __default__:
    subscription_id: "00000000-0000-0000-0000-000000000000"
    resource_group: "rg-dev"
    name: "aml-dev"
  prod:
    subscription_id: "11111111-1111-1111-1111-111111111111"
    resource_group: "rg-prod"
    name: "aml-prod"
```

A `__default__` entry is mandatory. Jobs reference a workspace by name; omitting the workspace falls back to `__default__`.

### Compute

```yaml
compute:
  __default__:
    cluster_name: "cpu-cluster"
  gpu:
    cluster_name: "gpu-cluster"
```

A `__default__` entry is mandatory. Jobs can override the compute target by referencing a named entry.

### Execution

```yaml
execution:
  environment: "my-env@latest"
  code_directory: "."           # path to upload, or null to disable
  working_directory: /home/kedro  # working dir inside the container
```

| Field | Default | Description |
|---|---|---|
| `environment` | `null` | Azure ML environment name (e.g. `my-env@latest`) |
| `code_directory` | `null` | Local directory to upload as code snapshot; `null` disables code upload |
| `working_directory` | `null` | Working directory inside the compute container |

### Jobs

Each entry in `jobs` maps to an Azure ML pipeline submission:

```yaml
jobs:
  training:
    pipeline:
      pipeline_name: "__default__"
      tags: ["training"]
    experiment_name: "training-experiment"
    display_name: "Daily training"
    compute: "gpu"                    # references a compute entry
    workspace: "prod"                 # references a workspace entry
    description: "Run the training pipeline on GPU"
    schedule:                         # inline schedule (or reference a named one)
      cron:
        expression: "0 8 * * 1-5"
        time_zone: "UTC"
```

#### Pipeline filter options

The `pipeline` section supports all Kedro pipeline filters:

| Field | Description |
|---|---|
| `pipeline_name` | Kedro pipeline name (default: `__default__`) |
| `from_nodes` | Start from these nodes |
| `to_nodes` | Run up to these nodes |
| `node_names` | Run only these specific nodes |
| `from_inputs` | Start from nodes that produce these datasets |
| `to_outputs` | Run up to nodes that produce these datasets |
| `node_namespaces` | Filter by namespace |
| `tags` | Filter by tag |

## CLI commands

All commands are available under `kedro azureml`:

### `kedro azureml init`

```text
kedro azureml init
```

Creates `conf/base/azureml.yml` (with placeholder values) and `.amlignore`.

### `kedro azureml compile`

```text
kedro azureml compile -j JOB_NAME [-o OUTPUT] [--params JSON] [--env-var KEY=VALUE] [--aml-env ENV]
```

Compiles named job(s) into Azure ML pipeline YAML definitions. Accepts multiple `-j` flags.

### `kedro azureml submit`

```text
kedro azureml submit -j JOB_NAME [--dry-run] [--once] [--wait-for-completion] [-w WORKSPACE] [--aml-env ENV] [--params JSON] [--env-var KEY=VALUE] [--on-job-scheduled MODULE:FUNC]
```

Submits named job(s) to Azure ML. Jobs with schedules create persistent Azure ML schedules; jobs without schedules run immediately.

| Flag | Description |
|---|---|
| `--dry-run` | Preview without submitting |
| `--once` | Force immediate run even if a schedule is configured |
| `--wait-for-completion` | Block until the run completes |
| `-w WORKSPACE` | Override workspace for all jobs in this batch |
| `--on-job-scheduled MODULE:FUNC` | Callback invoked after each job is scheduled |

### `kedro azureml execute` (internal)

Used internally by Azure ML pipeline steps to run individual Kedro nodes. Not intended for direct use.

## Scheduling

### Inline schedule

Attach a schedule directly to a job:

```yaml
jobs:
  nightly:
    pipeline:
      pipeline_name: "__default__"
    schedule:
      cron:
        expression: "0 2 * * *"
        time_zone: "UTC"
```

### Recurrence schedule

```yaml
jobs:
  weekly:
    pipeline:
      pipeline_name: "__default__"
    schedule:
      recurrence:
        frequency: "week"
        interval: 1
        schedule:
          week_days: ["Monday", "Wednesday", "Friday"]
          hours: [9]
          minutes: [0]
```

### Reusable schedule definitions

Define schedules once and reference them by name:

```yaml
schedules:
  business_hours:
    cron:
      expression: "0 9 * * 1-5"
      time_zone: "Europe/London"

jobs:
  training:
    pipeline:
      pipeline_name: "__default__"
    schedule: "business_hours"
```

## Data assets

### AzureMLAssetDataset

Use `AzureMLAssetDataset` in your Kedro catalog to read and write Azure ML data assets (`uri_file` or `uri_folder`):

```yaml
# conf/base/catalog.yml
model_input:
  type: kedro_azure_ml.datasets.AzureMLAssetDataset
  azureml_dataset: "my-dataset"
  version_type: "uri_folder"
  dataset:
    type: pandas.ParquetDataset
    filepath: "data.parquet"
```

The `AzureMLLocalRunHook` (registered in `settings.py`) automatically resolves data asset paths for local runs. During remote execution on Azure ML, the runner handles path injection via `--az-input` and `--az-output` flags.

## Distributed training

Decorate Kedro node functions with `@distributed_job` to run them as distributed training steps:

```python
from kedro_azure_ml.distributed import distributed_job, Framework

@distributed_job(framework=Framework.PyTorch, num_nodes=4)
def train_model(data):
    # Your distributed training code
    ...
```

Supported frameworks:

| Framework | Value |
|---|---|
| PyTorch | `Framework.PyTorch` |
| TensorFlow | `Framework.TensorFlow` |
| MPI | `Framework.MPI` |

The `num_nodes` and optional `processes_per_node` parameters control the distributed configuration.

## MLflow integration

When using [kedro-mlflow](https://kedro-mlflow.readthedocs.io/), Kedro Azure ML includes an `MlflowAzureMLHook` that coordinates experiment tracking:

- Sets the MLflow tracking URI to the Azure ML workspace
- Tags each child run with the Kedro node name
- Routes logs to the correct experiment

The hook activates automatically when the `KEDRO_AZURE_ML_MLFLOW_ENABLED` environment variable is set to `"1"` (injected by the pipeline generator during remote execution).

## Multiple workspaces

Define additional workspaces and reference them per-job:

```yaml
workspace:
  __default__:
    subscription_id: "..."
    resource_group: "rg-dev"
    name: "aml-dev"
  staging:
    subscription_id: "..."
    resource_group: "rg-staging"
    name: "aml-staging"

jobs:
  deploy:
    pipeline:
      pipeline_name: "deployment"
    workspace: "staging"
```

You can also override the workspace at submit time:

```bash
kedro azureml submit -j training -w staging
```

## Environment variables

Inject environment variables into Azure ML pipeline steps:

```bash
kedro azureml submit -j training --env-var API_KEY=secret --env-var DEBUG=1
```

## Troubleshooting

### Authentication errors

Ensure your Azure credentials are configured. Run `az login` or set up a service principal. The plugin uses `DefaultAzureCredential` from the Azure Identity SDK.

### Compute target not found

Verify the cluster name in your `azureml.yml` matches an existing compute target in your Azure ML workspace:

```bash
az ml compute list --workspace-name <name> --resource-group <rg>
```

### Environment not found

Check that the environment name (including version tag like `@latest`) exists in your Azure ML workspace:

```bash
az ml environment list --workspace-name <name> --resource-group <rg>
```

### Code upload issues

If files are missing during remote execution, check your `.amlignore` file. It controls which files are excluded from the code snapshot upload.

### Dataset version errors

When using `AzureMLAssetDataset`, ensure the referenced Azure ML data asset exists and the version is accessible. Check with:

```bash
az ml data show --name <dataset_name> --workspace-name <name> --resource-group <rg>
```

## Next steps

- [Getting Started](getting-started.md) for installation and first submission
- [API Reference](api-reference.md) for full module and class documentation
