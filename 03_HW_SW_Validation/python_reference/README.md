# Hardware software reference

`active_model_reference.py` rebuilds the selected local ECG Transformer and
loads the saved 6,643-parameter checkpoint in inference mode. It mirrors the
notebook's 198-sample ECG input, two RR features, eight heads, 16-dimensional
embedding, one encoder layer, 128-unit feed-forward layer, and five AAMI output
classes (`N`, `S`, `V`, `F`, `Q`). It does not train or download data.

To export the trained FP32 tensors and their shapes for the next hardware-port
stage, run from the project root:

```powershell
.venv\Scripts\python.exe 03_HW_SW_Validation\python_reference\export_active_model_weights.py
```

The output goes to `03_HW_SW_Validation\model_export\`. The export
is FP32 source data only. It is not an INT8 model and does not establish
quantized or FPGA accuracy. The former placeholder golden-vector generator
must not be used as model evidence.
