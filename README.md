# OrcaLab

OrcaLab is a front-end of OrcaGym. It provides a user-interface for scene assembling and simulation.

## Features

- TODO

## Requirements

- Python 3.12 or higher
- [OrcaGym](https://github.com/your-org/OrcaGym) (required dependency)
- Other dependencies listed in `pyproject.toml`

## Installation

1. Install OrcaGym (required):
	```bash
	# Please follow the OrcaGym installation instructions
	```
2. Clone this repository and install OrcaLab in editable mode:
	```bash
	# required by pyside
	sudo apt install libxcb-cursor0

	git clone https://github.com/openverse-orca/OrcaLab.git
	cd OrcaLab
	pip install -e .
	```


## Usage

To start OrcaLab, run:

```bash
python run.py
```


## Notice

- Blocking function (like QDialog.exec()) should wrap in `qasync.asyncWrap`.

``` python
def bloc_task():
	return dialog.exec()

await asyncWrap(bloc_task)
```

## License

This project is licensed under the terms of the [LICENSE](LICENSE) file.