# TurbineDAQ

A Python desktop app for automated turbine data acquisition in the UNH tow tank.

![Screenshot](https://raw.githubusercontent.com/petebachant/PhD-thesis/gh-pages/figures/TurbineDAQ.PNG)

## Test plan

A matrix of test parameters should be created and placed in the
`Test plan` directory inside of an experiment directory.
Each "section" of the experiment gets its own CSV file.
See `test/Test plan` for an
example.
The test plan, if one exists, is loaded into the GUI at startup.
To change, it must be
edited externally and reloaded.

Add stuff

## Directory and file structure

```
Experiment name/
    Config/
        Test plan/
            Top level.csv
            Perf-0.8.csv
            Tare_drag.csv
        fbg_properties.json
        turbine_properties.json
    Data/
        Processed/
            Perf-0.8.csv
            Tare_drag.csv
        Raw/
            Perf-0.8/
                0/
                    metadata.json
                    acsdata.h5
                    nidata.h5
                    vecdata.h5
                    fbgdata.h5
                    vecdata.vno
                1/
                    metadata.json
                    acsdata.h5
                    fbgdata.h5
                    nidata.h5
                    vecdata.h5
                    vecdata.vno
            Tare_drag/
                0/
                    metadata.json
                    acsdata.h5
                    nidata.h5
```

## Types of runs

In the `runtypes` module, there are classes to represent each type of run:

  * `TurbineTow`
  * `TareDragRun`
  * `TareTorqueRun`

Each of these subclass PyQt's `QThread`. For future experiments,
there will likely be
a `TurbineTowInWaves` or options in `TurbineTow` for wave generation with
`makewaves`.

## Developers

To get started, install a Python distribution that includes Conda or Mamba.
Miniforge is a good choice.
Next, create the `turbinedaq` conda environment with `conda env create` or
`mamba env create`.
Additional useful dev dependencies can be installed with
`pip install isort black`.
Next, install the `turbinedaq` package in editable mode with
`pip install -e .`.
The app can be run by running `turbinedaq` from the command line.
Note that the `turbinedaq` environment should be activated before installation
or running with `conda activate turbinedaq`.
