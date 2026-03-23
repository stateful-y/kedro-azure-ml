"""Kedro datasets for Azure ML pipeline data passing."""

from kedro_azure_ml.datasets.asset_dataset import AzureMLAssetDataset
from kedro_azure_ml.datasets.pipeline_dataset import AzureMLPipelineDataset

__all__ = [
    "AzureMLAssetDataset",
    "AzureMLPipelineDataset",
]
