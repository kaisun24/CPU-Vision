#!/usr/bin/env bash

set -e

eval "$(./conda/bin/conda shell.bash hook)"
conda activate ./env

python -m torch.utils.collect_env
PYTORCH_JIT_ENABLE_NVFUSER=0 pytest --junitxml=test-results/junit.xml -v --durations 20
