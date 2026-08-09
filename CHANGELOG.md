# Changelog

## Unreleased

### Build

- **requirements.txt** — `h5py==3.10.0` → `h5py>=3.11.0`. 3.10.0 has no `cp312/aarch64`
  wheel; Ubuntu noble uses Python 3.12, so pip attempted a source build under QEMU emulation
  which failed. 3.11.0 is the first release with a prebuilt `cp312-manylinux_aarch64` wheel.
- **requirements.txt** — `astroplan==0.10` → `astroplan==0.10.1` to drop its `numpy<2` cap.
  Pinned `numpy==1.26.4` (last stable 1.x; `astropy==6.0.1` still requires `numpy<2`).
  Pinned `matplotlib==3.9.2` and `pytz==2024.1` for reproducible cross-arch builds.
- **requirements.txt** — Removed `astroquery==0.4.7` (unused) and the `[recommended]` extra
  from `astropy` (pulls in `scipy`, which nothing in the codebase uses).
- **requirements.txt** — `requests==2.31.0` → `requests>=2.32.4` (security fix).
- **Dockerfile** — Added `gfortran` to the compile-stage `apt-get` for source-build fallbacks.
  Fixed `pip list` → `venv/bin/pip list` so the log shows venv packages.
- **.github/workflows/build-push.yaml** — Removed duplicate `Set up Docker Buildx` step.

### Fixed

- **comets.py** — `_compute_visual_magnitude` had two errors in the standard comet magnitude
  formula (`T = g + 5·log10(Δ) + k·log10(r)`): the geocentric (Δ) and heliocentric (r)
  distances were swapped, and `magnitude_k` was multiplied by an extra 2.5. Because the
  distances swap roles rather than shift the result by a constant, the error scrambled the
  comet ranking — comets closer to Earth were penalised and those farther from the Sun
  rewarded — so both the magnitude filter and the "brightest comet" selection operated on
  wrong data. Note: corrected magnitudes are still indicative; MPC g/k parameters can diverge
  significantly from JPL Horizons and from observer reports.

- **objects.py** — Polaris and custom targets were plotted on a new figure instead of the main
  sky map because `ax=ax` was missing from the `plot_sky` call.
- **bodies.py** — `_max_altitude` raised `UnboundLocalError` when a planet's meridian transit
  fell before the start of astronomical night. Added the missing `else` branch using the
  start-of-night position.
- **report.py** — `save_mqtt` mutated the shared result table by calling `remove_columns()`
  on it directly. Now operates on a `copy()` so later callers see the full table.
- **uptonight.py / objects.py / targets.py** — Mutable default arguments (`[]`, `{}`) in
  several method signatures replaced with `None` guards. Affected: `environment`, `constraints`,
  `bucket_list`, `done_list`, `custom_targets`.
- **comets.py** — Skyfield `Time` arrays compared with `<` raised `ValueError` for multi-event
  arrays. Fixed to compare `set_times[0].tt < rise_times[0].tt` when both arrays are non-empty.
- **comets.py** — Debug file `comets.txt` was always written to the current working directory
  instead of `output_dir`.
- **comets.py / bodies.py** — Skyfield ephemeris and MPC catalogue were loaded at class level,
  crashing the application at import time if the files were missing and the feature was
  disabled. Both now load inside `__init__`.
- **targets.py** — `_create_uptonight_comets_table` set the `azimuth` column format twice and
  never set `altitude`. Second duplicate replaced with the correct `altitude` assignment.

### Performance

- **comets.py** — Six separate `apply()` calls each re-propagated the comet orbit to compute
  one positional value. Replaced with `_compute_comet_ephemeris()` that propagates once and
  returns all six values (earth distance, sun distance, RA, Dec, altitude, azimuth) as a
  `pd.Series`. Reduces orbital propagations from 6× to 2× per comet.
- **comets.py** — Rise and set time were two separate `apply()` calls each running a full
  `find_discrete`. Merged into `_compute_rise_set_time()` returning both at once.
- **objects.py** — `observer.altaz()` was called three times with identical arguments for each
  deep-sky object. Single call stored in `altaz_start` and reused.

### Improvements

- **main.py** — Config-file parsing simplified: `~20` repeated `if cfg is not None and "key"
  in cfg.keys()…` guards replaced with a `_cfg_merge()` helper for dict sections and
  `cfg.get()` for scalar values. Removed a duplicate `colors` assignment.
- **main.py / targets.py** — `yaml.load(…, Loader=yaml.FullLoader)` replaced with
  `yaml.safe_load()` to prevent arbitrary Python object deserialisation from user config files.
- **main.py** — Exit code for missing longitude/latitude changed from `0` (success) to `1`
  (error). Fixed log message typo "Longitute" → "Longitude".
