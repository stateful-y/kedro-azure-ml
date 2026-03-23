# Getting Started

This guide walks you through installing Kedro Azure ML, configuring your Azure ML workspace, and submitting your first pipeline.

## Prerequisites

- Python 3.11+
- An existing [Kedro](https://kedro.org/) project
- An [Azure ML workspace](https://learn.microsoft.com/en-us/azure/machine-learning/concept-workspace) with at least one compute cluster
- Azure credentials configured (e.g. `az login` or a service principal)

## Installation

=== "pip"
    ```bash
    pip install kedro-azure-ml
    ```
=== "uv"
    ```bash
    uv add kedro-azure-ml
    ```

Verify the installation:

```bash
kedro azureml --help
```

## Initialize the configuration

From your Kedro project root, run:

```bash
kedro azureml init
```

This creates two files:

- `conf/base/azureml.yml`: workspace, compute, and execution settings (with placeholder values to fill in)
- `.amlignore`: controls which files are excluded from code upload

## Configuration overview

Open the generated `conf/base/azureml.yml` and replace the placeholders with your Azure details. It has three top-level sections:

```yaml
workspace:
  __default__:
    subscription_id: "<subscription_id>"
    resource_group: "<resource_group>"
    name: "<workspace_name>"

compute:
  __default__:
    cluster_name: "<cluster_name>"

execution:
  environment: "<azure_ml_environment>"
  code_directory: "."  # set to null to disable code upload
```

**workspace**: named workspace definitions. `__default__` is required; add more for multi-workspace setups.

**compute**: named compute clusters. `__default__` is required; jobs can reference other entries by name.

**execution**: the Azure ML environment and code upload settings.

## Register the hooks

Add the Kedro Azure ML hooks to your project's `settings.py`:

```python
from kedro_azure_ml.hooks import azureml_local_run_hook

HOOKS = (azureml_local_run_hook,)
```

This hook enables local runs with `AzureMLAssetDataset` entries in your catalog by transparently resolving Azure ML data asset paths.

## Define a job

Add a `jobs` section to `azureml.yml`:

```yaml
jobs:
  training:
    pipeline:
      pipeline_name: "__default__"
    experiment_name: "my-experiment"
    display_name: "Training pipeline"
```

Each job references a Kedro pipeline by name and optionally specifies an experiment, display name, compute override, or schedule.

### Pipeline filters

You can filter which nodes to include using the same options as `kedro run`:

```yaml
jobs:
  partial:
    pipeline:
      pipeline_name: "__default__"
      from_nodes: ["split_data"]
      tags: ["training"]
```

## Run on Azure ML

```bash
kedro azureml run -j training
```

Useful flags:

| Flag | Description |
|---|---|
| `--dry-run` | Preview what would be run without calling Azure ML |
| `--wait-for-completion` | Block until the pipeline run completes |
| `-w <name>` | Override the workspace for this run |
| `--aml-env <env>` | Override the Azure ML environment |
| `--params '{"key": "value"}'` | Pass runtime parameters as JSON |
| `--env-var KEY=VALUE` | Inject environment variables into pipeline steps |

To create or update a persistent schedule instead:

```bash
kedro azureml schedule -j training
```

## Compile to YAML

Export the Azure ML pipeline definition for inspection or CI integration:

```bash
kedro azureml compile -j training -o pipeline.yaml
```

## Next steps

- [User Guide](user-guide.md) for configuration reference, scheduling, distributed training, MLflow, and data assets
- [API Reference](api-reference.md) for full module and class documentation
