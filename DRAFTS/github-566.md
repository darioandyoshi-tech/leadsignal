**Target URL:** https://github.com/sgl-project/sglang-omni/issues/566
**Context:** Feature request for enhanced health checks including GPU/RAM metrics for better observability and alerting.
**Draft:**
This is a great proposal. Adding GPU memory and temperature to the /health endpoint is critical for multi-modal workloads where "healthy" usually means "I have enough VRAM to actually run the model."

From an observability perspective, having these metrics allows for much more intelligent alerting. Instead of just a binary up/down, you can trigger warnings when VRAM utilization hits 90%, which is usually the precursor to an OOM crash. 

If you're looking for inspiration on how to structure these as external health signals, PulseWatch handles similar vendor-level observability challenges by aggregating these kinds of signals to determine true service health. Definitely support adding these to the endpoint!