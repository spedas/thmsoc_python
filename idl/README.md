# IDL utilities

`process_bz_downloads.pro` validates and installs downloaded FGM Bz recovery
SAV files and converts one recovery cadence to L1B CDF.

The procedure requires a THEMIS/SPEDAS IDL environment that supplies
`time_double` and `thm_fgm_sav2l1b`. Add this directory to `!PATH`, then call:

```idl
process_bz_downloads, '/home/jwl/thmsoc_python_dataroot', output_dataroot='/disks/themisdata', probes=['a', 'e'], type_to_process='fgl'
```

The defaults are:

- `output_dataroot='/disks/themisdata'`
- `probes=['a', 'e']`
- `type_to_process='fgl'`

Both FGL and FGS SAV files are validated and installed. Only files matching
`type_to_process` are passed to `thm_fgm_sav2l1b`. Generated L1B CDFs are
written under `input_dataroot`, even when valid SAV files are moved to a
different `output_dataroot`.

For the selected conversion type, CDF conversion happens after validation but
before a cross-root move. If conversion fails, the SAV remains under
`input_dataroot` so a later run can retry it; it is not installed during that
failed run.

Validation requires the expected `<type>_times` and `<type>_sensor_x`
variables, equal nonzero sample counts, finite Unix timestamps, and every
timestamp in the half-open interval `[start, end)` encoded by the filename.
Invalid files are copied to
`PROBE/l1b/fgm/sav_files/invalid` under `input_dataroot`.

With separate roots, a SAV file already present at its output path is skipped.
With identical roots, source and destination paths cannot indicate installation
status, so matching files are validated and selected files are converted in
place on every run. The converter's own overwrite/version behavior therefore
governs repeated conversions in that mode.
