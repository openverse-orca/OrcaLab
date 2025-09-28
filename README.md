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

- Blocking function (like QDialog.exec()) should not be called in async function directly. It will stop the async loop in a strange way. There are two ways to work around:
	- wrap in `qasync.asyncWrap`
	- invoke by a qt signal.

``` python
# wrap in `qasync.asyncWrap`

async def foo():
	def bloc_task():
		return dialog.exec()

	await asyncWrap(bloc_task)	

# invoke by a qt signal

def bloc_task():
	return dialog.exec()

some_signal.connect(bloc_task)

```

## License

This project is licensed under the terms of the [LICENSE](LICENSE) file.