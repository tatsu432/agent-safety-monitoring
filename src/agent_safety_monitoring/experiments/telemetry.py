"""Only scalar aggregates and validated configuration metadata reach hosted tracking."""

import os
import re
import warnings


class Telemetry:
    def __init__(
        self,
        configuration,
        *,
        identity="development",
        split="development",
        shard=0,
        attempt="local",
        directory=None,
        metadata=None,
    ):
        self.run = None
        self.failure_type = None
        mode = os.environ.get("ASM_TRACKING_MODE", configuration.get("mode", "disabled"))
        self.mode = mode
        if mode not in {"disabled", "offline", "online"}:
            raise ValueError("Unknown tracking mode")
        if mode == "disabled":
            return
        try:
            import wandb

            from agent_safety_monitoring.monitors.core import MethodConfig

            settings = [
                MethodConfig.model_validate(m).model_dump()
                for m in (metadata or {}).get("method_settings", [])
            ]
            labels = []
            for method in settings:
                family = method["method"]
                suffix = {
                    "eae": f"-q{method['quote_tokens']}",
                    "average": f"-n{method['repeats']}",
                    "think": f"-{method['effort']}",
                    "mrt": f"-i{method['chunk_interactions']}",
                }.get(family, "")
                labels.append(family + suffix)
            label = "+".join(labels) or "monitor"
            # A unique attempt avoids offline resume's unsupported/ambiguous semantics.
            # The scientific identity groups attempts; persisted-result counts are cumulative.
            self.run = wandb.init(
                project="agent-safety-monitoring",
                mode=mode,
                id=attempt,
                group=identity,
                name=f"{split}-{label}-shard-{shard}-{attempt[:8]}",
                job_type=split,
                dir=str(directory) if directory else None,
                config={
                    "study_hash": identity,
                    "split": split,
                    "shard": shard,
                    "method_settings": settings,
                    **{
                        k: v
                        for k, v in (metadata or {}).items()
                        if k
                        in {
                            "model_revision",
                            "tokenizer_revision",
                            "engine_version",
                            "allocated_gpus",
                            "trajectory_concurrency",
                        }
                    },
                },
                settings=wandb.Settings(
                    console="off",
                    disable_code=True,
                    disable_git=True,
                    x_disable_stats=True,
                    init_timeout=10,
                ),
            )
        except Exception as exc:
            self.failure_type = type(exc).__name__
            warnings.warn(
                "Tracking initialization failed; local artifacts remain authoritative", stacklevel=2
            )

    def log(self, **metrics):
        # Neither arbitrary string values nor containers can enter a hosted run.
        fields = {
            "expected",
            "completed",
            "valid",
            "invalid",
            "remaining",
            "percent",
            "invalid_rate",
            "resumed",
            "logical_calls",
            "cache_hits",
            "input_tokens",
            "output_tokens",
            "reasoning_tokens",
            "reasoning_tokens_estimated",
            "reasoning_tokens_exposed",
            "reasoning_estimates_exposed",
            "output_retries",
            "request_latency_sum_seconds",
            "elapsed_seconds",
            "judgments_per_hour_estimate",
            "remaining_seconds_estimate",
            "attempted_calls",
            "failed_calls",
            "transport_retries",
            "gpu_count",
            "gpu_memory_mib",
            "gpu_peak_memory_mib",
            "gpu_utilization_percent",
        }
        categories = {
            "schema",
            "passage_index",
            "quotation_budget",
            "summary_budget",
            "citation",
            "truncation",
            "transport_server",
            "validation",
            "legacy_validation",
            "source_span",
        }
        allowed = {}
        for key, value in metrics.items():
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            prefix, _, field = key.rpartition("/")
            if (
                not prefix
                and key in fields
                or prefix == "attempt"
                and field in fields
                or prefix == "errors"
                and field in categories
                or re.fullmatch(r"(?:single|think|average|eae|mrt)-[a-f0-9]{12}", prefix)
                and field in fields
            ):
                allowed[key] = value
        if self.run:
            try:
                self.run.log(allowed)
            except Exception:
                warnings.warn("Tracking delivery failed; local artifacts preserved", stacklevel=2)
                self.close()

    def close(self):
        run, self.run = self.run, None
        if run:
            try:
                run.finish()
            except Exception:
                warnings.warn("Tracking close failed; local artifacts preserved", stacklevel=2)
