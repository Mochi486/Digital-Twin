# Streamlit dashboard summary

`dashboard/app.py` is a lightweight UI that imports existing scenario validation,
AI guard, SVG, dry-run, and generic simulator APIs rather than duplicating their
logic.  Start it from the project root:

```bash
streamlit run dashboard/app.py
```

The dashboard provides:

- project-facing Germany50 selected-path results, explicitly labelled as
  path-extracted rather than a full 50-node run;
- minimal RL reward, path selection, RTT, throughput, and baseline comparison;
- selection and schema/route validation of existing JSON scenarios, topology
  preview, dry-run, and an optional existing-simulator real run;
- guarded mock AI prompt generation followed by validation and dry-run;
- visible artifact locations and surfaced validation/run errors.

API keys are neither accepted by the page nor stored in session or artifacts.
Provider credentials remain environment variables consumed only by the existing
provider layer.  The page is deliberately small: it is an experiment browser and
safe control surface, not a second simulator implementation.
