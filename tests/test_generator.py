from unittest.mock import MagicMock, patch

import pytest
from azure.ai.ml.entities import Job
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from kedro_azureml_pipeline.config import ClusterConfig, RetryConfig
from kedro_azureml_pipeline.constants import (
    KEDRO_AZUREML_MLFLOW_ENABLED,
    KEDRO_AZUREML_MLFLOW_EXPERIMENT_NAME,
    KEDRO_AZUREML_MLFLOW_NODE_NAME,
    KEDRO_AZUREML_MLFLOW_RUN_NAME,
)
from kedro_azureml_pipeline.generator import AzureMLPipelineGenerator, ConfigException


class TestPipelineGeneration:
    """Core pipeline generation and Kedro integration."""

    @pytest.mark.parametrize(
        "pipeline_fixture",
        ["dummy_pipeline", "dummy_pipeline_compute_tag"],
    )
    def test_can_generate_azure_pipeline(
        self,
        pipeline_fixture,
        dummy_plugin_config,
        multi_catalog,
        request,
    ):
        pipeline = request.getfixturevalue(pipeline_fixture)
        aml_env = "unit_test/aml_env@latest"
        with patch.object(AzureMLPipelineGenerator, "get_kedro_pipeline", return_value=pipeline):
            env_name = "unit_test_env"
            generator = AzureMLPipelineGenerator(
                pipeline_fixture,
                env_name,
                dummy_plugin_config,
                {},
                catalog=multi_catalog,
                aml_env=aml_env,
            )

            az_pipeline = generator.generate()
            assert isinstance(az_pipeline, Job) and az_pipeline.display_name == pipeline_fixture, (
                "Invalid basic pipeline data"
            )
            assert all(f"kedro azureml -e {env_name} execute" in node.command for node in az_pipeline.jobs.values()), (
                "Commands seems invalid"
            )

            assert all(node.environment == aml_env for node in az_pipeline.jobs.values()), (
                "Invalid Azure ML Environment name set on commands"
            )

    def test_can_get_pipeline_from_kedro(self, dummy_plugin_config, dummy_pipeline, multi_catalog):
        pipeline_name = "unit_test_pipeline"
        with patch.dict("kedro.framework.project.pipelines", {pipeline_name: dummy_pipeline}):
            generator = AzureMLPipelineGenerator(pipeline_name, "local", dummy_plugin_config, {}, catalog=multi_catalog)
            p = generator.get_kedro_pipeline()
            assert p == dummy_pipeline

    def test_deterministic_node_tag(self, dummy_pipeline_deterministic_tag, dummy_plugin_config, multi_catalog):
        """Nodes tagged 'deterministic' propagate the flag to the generated Azure pipeline."""
        with patch.object(
            AzureMLPipelineGenerator,
            "get_kedro_pipeline",
            return_value=dummy_pipeline_deterministic_tag,
        ):
            generator = AzureMLPipelineGenerator(
                "dummy_pipeline_deterministic_tag",
                "unit_test_env",
                dummy_plugin_config,
                {},
                catalog=multi_catalog,
                aml_env="unit_test/aml_env@latest",
            )

            az_pipeline = generator.generate()
            for node in dummy_pipeline_deterministic_tag.nodes:
                assert az_pipeline.jobs[node.name].component.is_deterministic == ("deterministic" in node.tags), (
                    "is_deterministic property does not match node tag"
                )


class TestComputeResources:
    """Compute-tag routing and multi-compute error handling."""

    def test_different_compute_per_node(self, dummy_pipeline_compute_tag, dummy_plugin_config, multi_catalog):
        """A node tagged with a compute tag is routed to the matching cluster."""
        dummy_plugin_config.compute.root["compute-2"] = ClusterConfig(cluster_name="cpu-cluster-2")
        with patch.object(
            AzureMLPipelineGenerator,
            "get_kedro_pipeline",
            return_value=dummy_pipeline_compute_tag,
        ):
            generator = AzureMLPipelineGenerator(
                "dummy_pipeline_compute_tag",
                "unit_test_env",
                dummy_plugin_config,
                {},
                catalog=multi_catalog,
                aml_env="unit_test/aml_env@latest",
            )

            az_pipeline = generator.generate()
            for node in dummy_pipeline_compute_tag.nodes:
                if node.tags:
                    assert all(
                        dummy_plugin_config.compute.root[tag].cluster_name == az_pipeline.jobs[node.name]["compute"]
                        for tag in node.tags
                    ), "compute settings don't match"

    def test_multiple_compute_tags_raises(self, dummy_plugin_config, dummy_pipeline, multi_catalog):
        """A node with more than one compute tag causes a ConfigException."""
        pipeline_name = "unit_test_pipeline"
        node = MagicMock()
        node.tags = ["compute-2", "compute-3"]
        for t in node.tags:
            dummy_plugin_config.compute.root[t] = ClusterConfig(cluster_name=t)
        with patch.dict("kedro.framework.project.pipelines", {pipeline_name: dummy_pipeline}):
            generator = AzureMLPipelineGenerator(pipeline_name, "local", dummy_plugin_config, {}, catalog=multi_catalog)
            with pytest.raises(ConfigException):
                generator.get_target_resource_from_node_tags(node)


class TestEnvironmentVariables:
    """Custom and auto-injected environment variables on generated nodes."""

    def test_custom_env_vars_propagated(self, dummy_plugin_config, dummy_pipeline, multi_catalog):
        pipeline_name = "unit_test_pipeline"
        with patch.dict("kedro.framework.project.pipelines", {pipeline_name: dummy_pipeline}):
            generator = AzureMLPipelineGenerator(
                pipeline_name,
                "local",
                dummy_plugin_config,
                {},
                extra_env={"ABC": "def"},
                catalog=multi_catalog,
            )

            for node in generator.generate().jobs.values():
                assert node.environment_variables["ABC"] == "def"

    def test_retry_settings_applied_to_all_steps(self, dummy_plugin_config, dummy_pipeline, multi_catalog):
        """When retry_config is set, every step gets RetrySettings."""
        retry = RetryConfig(max_retries=3, timeout=1800)
        with patch.object(AzureMLPipelineGenerator, "get_kedro_pipeline", return_value=dummy_pipeline):
            generator = AzureMLPipelineGenerator(
                "test_retry",
                "local",
                dummy_plugin_config,
                {},
                catalog=multi_catalog,
                aml_env="test@latest",
                retry_config=retry,
            )
            az_pipeline = generator.generate()
            for step in az_pipeline.jobs.values():
                assert step.retry_settings is not None
                assert step.retry_settings.max_retries == 3
                assert step.retry_settings.timeout == 1800

    def test_no_retry_by_default(self, dummy_plugin_config, dummy_pipeline, multi_catalog):
        """Without retry_config, steps have no retry settings."""
        with patch.object(AzureMLPipelineGenerator, "get_kedro_pipeline", return_value=dummy_pipeline):
            generator = AzureMLPipelineGenerator(
                "test_no_retry",
                "local",
                dummy_plugin_config,
                {},
                catalog=multi_catalog,
                aml_env="test@latest",
            )
            az_pipeline = generator.generate()
            for step in az_pipeline.jobs.values():
                assert not step.retry_settings

    def test_retry_without_timeout(self, dummy_plugin_config, dummy_pipeline, multi_catalog):
        """RetryConfig with only max_retries sets timeout to None."""
        retry = RetryConfig(max_retries=2)
        with patch.object(AzureMLPipelineGenerator, "get_kedro_pipeline", return_value=dummy_pipeline):
            generator = AzureMLPipelineGenerator(
                "test_retry_no_timeout",
                "local",
                dummy_plugin_config,
                {},
                catalog=multi_catalog,
                aml_env="test@latest",
                retry_config=retry,
            )
            az_pipeline = generator.generate()
            for step in az_pipeline.jobs.values():
                assert step.retry_settings is not None
                assert step.retry_settings.max_retries == 2
                assert step.retry_settings.timeout is None

    def test_auto_sets_kedro_env(self, dummy_plugin_config, dummy_pipeline, multi_catalog):
        pipeline_name = "unit_test_pipeline"
        with patch.dict("kedro.framework.project.pipelines", {pipeline_name: dummy_pipeline}):
            generator = AzureMLPipelineGenerator(
                pipeline_name,
                "dev",
                dummy_plugin_config,
                {},
                catalog=multi_catalog,
            )

            for node in generator.generate().jobs.values():
                assert node.environment_variables["KEDRO_ENV"] == "dev"

    def test_explicit_kedro_env_overrides_auto(self, dummy_plugin_config, dummy_pipeline, multi_catalog):
        pipeline_name = "unit_test_pipeline"
        with patch.dict("kedro.framework.project.pipelines", {pipeline_name: dummy_pipeline}):
            generator = AzureMLPipelineGenerator(
                pipeline_name,
                "dev",
                dummy_plugin_config,
                {},
                extra_env={"KEDRO_ENV": "staging"},
                catalog=multi_catalog,
            )

            for node in generator.generate().jobs.values():
                assert node.environment_variables["KEDRO_ENV"] == "staging"


class TestFactoryPatternHandling:
    """Catalog factory-resolved inputs are treated as plain string parameters."""

    def test_factory_resolved_input_is_string_type(self, dummy_pipeline, dummy_plugin_config, factory_catalog):
        """A pipeline input resolved via a catalog factory pattern (not in catalog.filter())
        must be treated as a non-AzureML string input, not as a uri_folder."""
        pipeline_name = "unit_test_pipeline"
        with patch.dict("kedro.framework.project.pipelines", {pipeline_name: dummy_pipeline}):
            generator = AzureMLPipelineGenerator(
                pipeline_name,
                "local",
                dummy_plugin_config,
                {},
                catalog=factory_catalog,
                aml_env="unit_test/aml_env@latest",
            )
            assert "input_data" not in factory_catalog.filter()
            assert "input_data" in factory_catalog  # factory resolves it
            assert generator._is_param_or_root_non_azureml_asset_dataset("input_data", dummy_pipeline), (
                "Factory-resolved pipeline input should be treated as a non-AzureML string input"
            )
            inp = generator._get_input("input_data", dummy_pipeline)
            assert inp.type == "string", (
                f"Expected 'string' input type for factory-resolved pipeline input, got '{inp.type}'"
            )


class TestUriFileRestrictions:
    """``uri_file`` assets have input-only and no-output constraints."""

    def test_uri_file_non_input_raises(self, dummy_pipeline, dummy_plugin_config):
        """A ``uri_file`` used as intermediate data (not a pipeline input) should raise."""
        from kedro.io import DataCatalog
        from kedro.io.core import Version
        from kedro_datasets.pickle import PickleDataset

        from kedro_azureml_pipeline.datasets import AzureMLAssetDataset

        # i2 is an intermediate dataset (not in pipeline.inputs())
        uri_file_ds = AzureMLAssetDataset(
            dataset={"type": PickleDataset, "filepath": "test.pickle"},
            azureml_dataset="test_ds",
            version=Version(None, None),
            azureml_type="uri_file",
        )
        catalog = DataCatalog({"input_data": MagicMock(), "i2": uri_file_ds})

        generator = AzureMLPipelineGenerator(
            "test",
            "local",
            dummy_plugin_config,
            {},
            catalog=catalog,
        )
        with pytest.raises(ValueError, match="uri_file.*can only be used as pipeline inputs"):
            generator._get_input("i2", dummy_pipeline)

    def test_uri_file_output_raises(self, dummy_plugin_config):
        """A ``uri_file`` used as output should raise."""
        from kedro.io import DataCatalog
        from kedro.io.core import Version
        from kedro_datasets.pickle import PickleDataset

        from kedro_azureml_pipeline.datasets import AzureMLAssetDataset

        uri_file_ds = AzureMLAssetDataset(
            dataset={"type": PickleDataset, "filepath": "test.pickle"},
            azureml_dataset="test_ds",
            version=Version(None, None),
            azureml_type="uri_file",
        )
        catalog = DataCatalog({"output_data": uri_file_ds})

        generator = AzureMLPipelineGenerator(
            "test",
            "local",
            dummy_plugin_config,
            {},
            catalog=catalog,
        )
        with pytest.raises(ValueError, match="uri_file.*cannot be used as outputs"):
            generator._get_output("output_data")


class TestMlflowEnvVarInjection:
    """Test that the generator injects MLflow env vars into each node."""

    def test_mlflow_env_vars_injected_when_enabled(self, dummy_plugin_config, dummy_pipeline, multi_catalog):
        pipeline_name = "unit_test_pipeline"

        with patch.dict("kedro.framework.project.pipelines", {pipeline_name: dummy_pipeline}):
            generator = AzureMLPipelineGenerator(
                pipeline_name,
                "local",
                dummy_plugin_config,
                {},
                catalog=multi_catalog,
                mlflow_run_name="my-run",
                experiment_name="my-experiment",
            )
            az_pipeline = generator.generate()

        for node_name, node_job in az_pipeline.jobs.items():
            env = node_job.environment_variables
            assert env[KEDRO_AZUREML_MLFLOW_ENABLED] == "1"
            assert env[KEDRO_AZUREML_MLFLOW_RUN_NAME] == "my-run"
            assert env[KEDRO_AZUREML_MLFLOW_EXPERIMENT_NAME] == "my-experiment"
            assert env[KEDRO_AZUREML_MLFLOW_NODE_NAME] == node_name

    def test_mlflow_env_vars_absent_when_no_experiment(self, dummy_plugin_config, dummy_pipeline, multi_catalog):
        pipeline_name = "unit_test_pipeline"

        with patch.dict("kedro.framework.project.pipelines", {pipeline_name: dummy_pipeline}):
            generator = AzureMLPipelineGenerator(
                pipeline_name,
                "local",
                dummy_plugin_config,
                {},
                catalog=multi_catalog,
            )
            az_pipeline = generator.generate()

        for node_job in az_pipeline.jobs.values():
            env = node_job.environment_variables
            assert KEDRO_AZUREML_MLFLOW_ENABLED not in env
            assert KEDRO_AZUREML_MLFLOW_RUN_NAME not in env

    def test_mlflow_empty_experiment_name_skips_experiment_env(
        self, dummy_plugin_config, dummy_pipeline, multi_catalog
    ):
        """When ``experiment_name=""`` (falsy but not None), MLFLOW_EXPERIMENT_NAME is omitted."""
        pipeline_name = "unit_test_pipeline"

        with patch.dict("kedro.framework.project.pipelines", {pipeline_name: dummy_pipeline}):
            generator = AzureMLPipelineGenerator(
                pipeline_name,
                "local",
                dummy_plugin_config,
                {},
                catalog=multi_catalog,
                experiment_name="",
            )
            az_pipeline = generator.generate()

        for node_job in az_pipeline.jobs.values():
            env = node_job.environment_variables
            assert env[KEDRO_AZUREML_MLFLOW_ENABLED] == "1"
            assert KEDRO_AZUREML_MLFLOW_EXPERIMENT_NAME not in env

    def test_mlflow_node_name_unique_per_node(self, dummy_plugin_config, dummy_pipeline, multi_catalog):
        pipeline_name = "unit_test_pipeline"

        with patch.dict("kedro.framework.project.pipelines", {pipeline_name: dummy_pipeline}):
            generator = AzureMLPipelineGenerator(
                pipeline_name,
                "local",
                dummy_plugin_config,
                {},
                catalog=multi_catalog,
                experiment_name="my-experiment",
            )
            az_pipeline = generator.generate()

        node_names = {
            node_job.environment_variables[KEDRO_AZUREML_MLFLOW_NODE_NAME] for node_job in az_pipeline.jobs.values()
        }
        assert len(node_names) == len(az_pipeline.jobs), "Each node should have a unique MLFLOW_NODE_NAME"


class TestSanitizeFunctions:
    """Property-based tests for name sanitisation functions."""

    @given(name=st.text(min_size=1, max_size=50))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_sanitize_param_name_always_lowercase_alphanumeric(self, name, dummy_plugin_config, multi_catalog):
        """_sanitize_param_name always produces lowercase alphanumeric + underscore."""
        generator = AzureMLPipelineGenerator(
            "test",
            "env",
            dummy_plugin_config,
            {},
            catalog=multi_catalog,
        )
        result = generator._sanitize_param_name(name)
        assert result == result.lower()
        assert all(c.isalnum() or c == "_" for c in result)
        assert len(result) == len(name)

    @given(name=st.text(min_size=1, max_size=50))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_sanitize_azure_name_always_lowercase(self, name, dummy_plugin_config, multi_catalog):
        """_sanitize_azure_name always produces a lowercase string with no dots."""
        generator = AzureMLPipelineGenerator(
            "test",
            "env",
            dummy_plugin_config,
            {},
            catalog=multi_catalog,
        )
        result = generator._sanitize_azure_name(name)
        assert result == result.lower()
        assert "." not in result


class TestGetKedroParam:
    """_get_kedro_param resolves dot-separated paths through dicts and objects.

    Kedro 1.3+ allows Pydantic models as parameter values. The generator must
    traverse both dicts (plain YAML) and objects (Pydantic) when resolving
    ``params:`` references used in ``@distributed_job`` decorators.
    """

    def _make_generator(self, kedro_params, dummy_plugin_config, multi_catalog):
        return AzureMLPipelineGenerator(
            "test",
            "local",
            dummy_plugin_config,
            kedro_params,
            catalog=multi_catalog,
        )

    def test_flat_dict_lookup(self, dummy_plugin_config, multi_catalog):
        gen = self._make_generator({"num_nodes": 4}, dummy_plugin_config, multi_catalog)
        assert gen._get_kedro_param("num_nodes") == 4

    def test_nested_dict_lookup(self, dummy_plugin_config, multi_catalog):
        params = {"a": {"b": {"c": 42}}}
        gen = self._make_generator(params, dummy_plugin_config, multi_catalog)
        assert gen._get_kedro_param("a.b.c") == 42

    def test_pydantic_model_lookup(self, dummy_plugin_config, multi_catalog):
        """Traverses a Pydantic BaseModel via attribute access."""
        from pydantic import BaseModel

        class Inner(BaseModel):
            num_nodes: int = 3

        class Outer(BaseModel):
            tuning: Inner = Inner()

        params = {"spec": Outer()}
        gen = self._make_generator(params, dummy_plugin_config, multi_catalog)
        assert gen._get_kedro_param("spec.tuning.num_nodes") == 3

    def test_mixed_dict_and_pydantic(self, dummy_plugin_config, multi_catalog):
        """Dict at the top level, Pydantic model nested inside."""
        from pydantic import BaseModel

        class Config(BaseModel):
            value: int = 7

        params = {"product": {"group": {"variant": {"spec": Config()}}}}
        gen = self._make_generator(params, dummy_plugin_config, multi_catalog)
        assert gen._get_kedro_param("product.group.variant.spec.value") == 7

    def test_explicit_params_arg(self, dummy_plugin_config, multi_catalog):
        """Passing an explicit params dict overrides kedro_params."""
        gen = self._make_generator({"x": 1}, dummy_plugin_config, multi_catalog)
        assert gen._get_kedro_param("y", params={"y": 99}) == 99

    def test_missing_key_raises(self, dummy_plugin_config, multi_catalog):
        gen = self._make_generator({}, dummy_plugin_config, multi_catalog)
        with pytest.raises(KeyError):
            gen._get_kedro_param("missing")

    def test_missing_attr_on_object_raises(self, dummy_plugin_config, multi_catalog):
        from pydantic import BaseModel

        class Spec(BaseModel):
            x: int = 1

        gen = self._make_generator({"spec": Spec()}, dummy_plugin_config, multi_catalog)
        with pytest.raises(AttributeError):
            gen._get_kedro_param("spec.nonexistent")

    def test_single_level_pydantic_attr(self, dummy_plugin_config, multi_catalog):
        """Flat lookup on a Pydantic model passed via explicit params."""
        from pydantic import BaseModel

        class Cfg(BaseModel):
            n: int = 5

        gen = self._make_generator({}, dummy_plugin_config, multi_catalog)
        assert gen._get_kedro_param("n", params=Cfg()) == 5

    def test_dataclass_attr_lookup(self, dummy_plugin_config, multi_catalog):
        """Supports plain dataclasses (not only Pydantic)."""
        from dataclasses import dataclass

        @dataclass
        class Settings:
            num_nodes: int = 10

        params = {"settings": Settings()}
        gen = self._make_generator(params, dummy_plugin_config, multi_catalog)
        assert gen._get_kedro_param("settings.num_nodes") == 10

    def test_deeply_nested_pydantic(self, dummy_plugin_config, multi_catalog):
        """Four levels of Pydantic nesting."""
        from pydantic import BaseModel

        class D(BaseModel):
            val: int = 99

        class C(BaseModel):
            d: D = D()

        class B(BaseModel):
            c: C = C()

        class A(BaseModel):
            b: B = B()

        gen = self._make_generator({"a": A()}, dummy_plugin_config, multi_catalog)
        assert gen._get_kedro_param("a.b.c.d.val") == 99


class TestFromParamsOrValue:
    """_from_params_or_value resolves params: references or returns literals."""

    def _make_generator(self, kedro_params, dummy_plugin_config, multi_catalog):
        return AzureMLPipelineGenerator(
            "test",
            "local",
            dummy_plugin_config,
            kedro_params,
            catalog=multi_catalog,
        )

    def test_literal_int(self, dummy_plugin_config, multi_catalog):
        gen = self._make_generator({}, dummy_plugin_config, multi_catalog)
        assert gen._from_params_or_value(None, 5, hint="num_nodes") == 5

    def test_params_reference_no_namespace(self, dummy_plugin_config, multi_catalog):
        gen = self._make_generator({"num_nodes": 8}, dummy_plugin_config, multi_catalog)
        assert gen._from_params_or_value(None, "params:num_nodes", hint="num_nodes") == 8

    def test_params_reference_with_namespace(self, dummy_plugin_config, multi_catalog):
        params = {"product": {"group": {"variant": {"spec": {"tuning": {"num_nodes": 3}}}}}}
        gen = self._make_generator(params, dummy_plugin_config, multi_catalog)
        result = gen._from_params_or_value(
            "product.group.variant",
            "params:spec.tuning.num_nodes",
            hint="num_nodes",
        )
        assert result == 3

    def test_params_reference_with_pydantic_namespace(self, dummy_plugin_config, multi_catalog):
        """Namespace traversal through Pydantic models (Kedro 1.3 params)."""
        from pydantic import BaseModel

        class TuningConfig(BaseModel):
            num_nodes: int = 2

        class VariantSpec(BaseModel):
            tuning: TuningConfig = TuningConfig()

        params = {"product": {"group": {"variant": {"spec": VariantSpec()}}}}
        gen = self._make_generator(params, dummy_plugin_config, multi_catalog)
        result = gen._from_params_or_value(
            "product.group.variant",
            "params:spec.tuning.num_nodes",
            hint="num_nodes",
        )
        assert result == 2

    def test_wrong_type_raises(self, dummy_plugin_config, multi_catalog):
        gen = self._make_generator({}, dummy_plugin_config, multi_catalog)
        with pytest.raises(ValueError, match="Expected either"):
            gen._from_params_or_value(None, 3.14, hint="num_nodes")

    def test_bool_is_not_int(self, dummy_plugin_config, multi_catalog):
        """bool is rejected when expected_value_type is int (strict type() check)."""
        gen = self._make_generator({}, dummy_plugin_config, multi_catalog)
        with pytest.raises(ValueError, match="Expected either"):
            gen._from_params_or_value(None, True, hint="num_nodes")

    def test_params_ref_mixed_pydantic_and_dict(self, dummy_plugin_config, multi_catalog):
        """Dict at top, Pydantic in middle, dict at bottom."""
        from pydantic import BaseModel

        class Middle(BaseModel):
            inner: dict = {"count": 6}

        params = {"ns": {"spec": Middle()}}
        gen = self._make_generator(params, dummy_plugin_config, multi_catalog)
        result = gen._from_params_or_value("ns", "params:spec.inner.count", hint="count")
        assert result == 6
