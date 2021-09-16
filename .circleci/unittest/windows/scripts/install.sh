#!/usr/bin/env bash

unset PYTORCH_VERSION
# For unittest, nightly PyTorch is used as the following section,
# so no need to set PYTORCH_VERSION.
# In fact, keeping PYTORCH_VERSION forces us to hardcode PyTorch version in config.

set -ex

this_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

eval "$(./conda/Scripts/conda.exe 'shell.bash' 'hook')"
conda activate ./env

if [ "${CU_VERSION:-}" == "cpu" ] ; then
    cudatoolkit="cpuonly"
else
    if [[ ${#CU_VERSION} -eq 4 ]]; then
        CUDA_VERSION="${CU_VERSION:2:1}.${CU_VERSION:3:1}"
    elif [[ ${#CU_VERSION} -eq 5 ]]; then
        CUDA_VERSION="${CU_VERSION:2:2}.${CU_VERSION:4:1}"
    fi
    echo "Using CUDA $CUDA_VERSION as determined by CU_VERSION"
    version="$(python -c "print('.'.join(\"${CUDA_VERSION}\".split('.')[:2]))")"
    cudatoolkit="cudatoolkit=${version}"
fi

printf "Installing PyTorch with %s\n" "${cudatoolkit}"
conda install -y -c "pytorch-${UPLOAD_CHANNEL}" -c conda-forge "pytorch-${UPLOAD_CHANNEL}"::pytorch "${cudatoolkit}" pytest

export cuda_available=$(python -c "import torch; print(torch.cuda.is_available())")
echo "cuda available is" $cuda_available

if [ $PYTHON_VERSION == "3.6" ]; then
    printf "Installing minimal PILLOW version\n"
    # Install the minimal PILLOW version. Otherwise, let setup.py install the latest
    pip install pillow>=5.3.0
fi

printf "* Installing torchvision\n"
"$this_dir/set_cuda_envs.sh"
"$this_dir/vc_env_helper.bat" python setup.py develop
