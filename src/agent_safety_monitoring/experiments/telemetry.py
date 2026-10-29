"""Aggregate-only tracking; caller never supplies arbitrary benchmark content."""

import warnings


class Telemetry:
    def __init__(self, configuration):
        self.run = None
        mode = configuration.get("mode", "disabled")
        if mode not in {"disabled", "offline", "online"}:
            raise ValueError("Unknown tracking mode")
        if mode != "disabled":
            try:
                import wandb

                self.run = wandb.init(
                    project=configuration.get("project", "agent-safety-monitoring"),
                    mode=mode,
                    settings=wandb.Settings(console="off"),
                )
            except Exception:
                warnings.warn(
                    "Tracking initialization failed; local artifacts remain authoritative",
                    stacklevel=2,
                )

    def log(self, *, completed, invalid, input_tokens, output_tokens, logical_calls):
        if self.run:
            try:
                self.run.log(
                    {
                        "completed": completed,
                        "invalid": invalid,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "logical_calls": logical_calls,
                    }
                )
            except Exception:
                warnings.warn("Tracking delivery failed; local artifacts preserved", stacklevel=2)

    def close(self):
        if self.run:
            try:
                self.run.finish()
            except Exception:
                warnings.warn("Tracking close failed; local artifacts preserved", stacklevel=2)
