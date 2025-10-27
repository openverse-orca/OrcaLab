# OrcaLab

OrcaLab is a front-end of OrcaGym. It provides a user-interface for scene assembling and simulation.

## Features

- TODO

## Requirements

- Python 3.12 or higher
- [OrcaGym](https://github.com/your-org/OrcaGym) (required dependency)
- Other dependencies listed in `pyproject.toml`

## Development Requirements

For building and releasing packages, the following pip packages are required:

### Core Build Tools
```bash
pip install build twine wheel setuptools
```

### Development Tools (Optional)
```bash
pip install pytest pytest-cov flake8 black mypy
```

### Make Commands and Required Packages

The project includes a `Makefile` with various commands. Here are the required packages for each command:

| Make Command | Required pip packages | Description |
|-------------|----------------------|-------------|
| `make build` | `build`, `setuptools`, `wheel` | Build distribution packages |
| `make check` | `twine` | Check package quality |
| `make test-install` | `build`, `setuptools`, `wheel` | Test local installation |
| `make test-install-testpypi` | `build`, `setuptools`, `wheel` | Test TestPyPI installation |
| `make test-install-pypi` | `build`, `setuptools`, `wheel` | Test PyPI installation |
| `make release-test` | `build`, `twine`, `setuptools`, `wheel` | Release to TestPyPI |
| `make release-prod` | `build`, `twine`, `setuptools`, `wheel` | Release to PyPI |
| `make bump-version` | None (uses sed) | Bump version number |
| `make setup-pypirc` | None | Setup PyPI configuration file |
| `make check-pypirc` | None | Check PyPI configuration |
| `make clean` | None | Clean build artifacts |
| `make test` | `pytest`, `pytest-cov` | Run tests |
| `make format` | `black` | Format code |
| `make lint` | `flake8`, `mypy` | Lint code |

### Quick Setup for Development
```bash
# Install development dependencies
pip install build twine wheel setuptools pytest pytest-cov flake8 black mypy

# Or install from the project's optional dependencies
pip install -e ".[dev]"
```

## Release Process

### Quick Release
```bash
# Setup PyPI configuration (first time only)
make setup-pypirc

# Release to TestPyPI
./scripts/release/release.sh test

# Release to PyPI
./scripts/release/release.sh prod
```

### Step-by-step Release
```bash
# Clean, build, check, and upload
./scripts/release/clean.sh
./scripts/release/build.sh
./scripts/release/check.sh
./scripts/release/upload_test.sh  # or upload_prod.sh
```

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

## 常见问题

### Linux上出现 version `GLIBCXX_3.4.30' not found
    conda update -c conda-forge libstdcxx-ng



## License

This project is licensed under the terms of the [LICENSE](LICENSE) file.