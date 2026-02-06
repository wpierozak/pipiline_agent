# Pipeline Agent Package Files

This directory contains packaging configuration files for distributing Pipeline Agent as a Python library.

## Files Created

### `pyproject.toml`
Modern Python packaging configuration (PEP 518/621 compliant):
- Package metadata (name, version, description)
- Dependencies specification
- Build system configuration
- Optional development dependencies
- Classifiers for PyPI

### `requirements.txt`
Direct dependency list for development or non-pip installations.

### `__init__.py` files
Created in each module to make them proper Python packages:
- Main package root
- All submodules (agent, chat, cmd_line, coding, core, config, directory, embeddings, jenkins_utils)

## Installation Options

### Install in Development Mode
```bash
pip install -e .
```

### Install from Source
```bash
pip install .
```

### Build Distribution
```bash
python -m build
```

### Install from GitHub
```bash
pip install git+https://github.com/wpierozak/pipiline_agent.git
```

## Publishing to PyPI (Optional)

1. Build the package:
```bash
python -m build
```

2. Upload to PyPI:
```bash
python -m twine upload dist/*
```

## Version Management

Update version in `pyproject.toml` and `__init__.py` when releasing new versions.
