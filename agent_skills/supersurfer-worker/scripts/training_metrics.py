"""Copy into the reviewed project and call from its measured training loop.

No architecture or device FLOPs are guessed. The caller supplies global model
FLOPs per optimizer step and aggregate device peak FLOP/s at training precision.
Use the slowest synchronized rank's step time, including gradient accumulation.
"""
import math


def log_training_step(run, *, step, model_flops_per_step, peak_flops_per_second,
                      step_seconds, samples_per_step=None, allocated_bytes=None,
                      reserved_bytes=None):
    for name, value in (("model_flops_per_step", model_flops_per_step),
                        ("peak_flops_per_second", peak_flops_per_second),
                        ("step_seconds", step_seconds)):
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(name + " must be a positive finite measurement or documented estimate")
    metrics = {"train/mfu": model_flops_per_step / step_seconds / peak_flops_per_second,
               "perf/step_seconds": step_seconds}
    for key, value in (("perf/samples_per_second", None if samples_per_step is None else samples_per_step / step_seconds),
                       ("gpu/allocated_bytes", allocated_bytes), ("gpu/reserved_bytes", reserved_bytes)):
        if value is not None:
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError(key + " must be finite and nonnegative")
            metrics[key] = value
    run.log(metrics, step=step)
    return metrics
