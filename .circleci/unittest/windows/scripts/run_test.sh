#!/usr/bin/env bash

set -e

eval "$(./conda/Scripts/conda.exe 'shell.bash' 'hook')"
conda activate ./env

conda remove -y ffmpeg
python -m torch.utils.collect_env
pytest --cov=torchvision --junitxml=test-results/junit.xml -v --durations 20 test --ignore=test/test_datasets_download.py