#!/bin/bash
set -ex

if [[ "$(uname)" != Darwin && "$OSTYPE" != "msys" ]]; then
    eval "$(./conda/bin/conda shell.bash hook)"
    conda activate ./env
fi

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
. "$script_dir/pkg_helpers.bash"

export BUILD_TYPE=conda
setup_env 0.8.0
export SOURCE_ROOT_DIR="$PWD"
setup_conda_pytorch_constraint
setup_conda_cudatoolkit_plain_constraint

if [[ "$OSTYPE" == "msys" ]]; then
    conda install -yq conda-build cmake
fi

setup_visual_studio_constraint
setup_junit_results_folder

conda install -yq pytorch=$PYTORCH_VERSION $CONDA_CUDATOOLKIT_CONSTRAINT $CONDA_CPUONLY_FEATURE  -c pytorch-nightly
TORCH_PATH=$(dirname $(python -c "import torch; print(torch.__file__)"))

if [[ "$(uname)" == Darwin || "$OSTYPE" == "msys" ]]; then
    conda install -yq libpng jpeg
else
    yum install -y libpng-devel libjpeg-turbo-devel
fi

mkdir cpp_build
pushd cpp_build

# Generate libtorchvision files
cmake .. -DTorch_DIR=$TORCH_PATH/share/cmake/Torch -DWITH_CUDA=$CMAKE_USE_CUDA

# Compile and install libtorchvision
if [[ "$OSTYPE" == "msys" ]]; then
    "$script_dir/windows/internal/vc_env_helper.bat" "$script_dir/windows/internal/build_cmake.bat"
else
    make
    make install

    if [[ "$(uname)" == Darwin ]]; then
        CONDA_PATH=$(dirname $(dirname $(which python)))
        cp -r /usr/local/include/torchvision $CONDA_PATH/include/
    fi
fi

popd

# Install torchvision locally
python setup.py develop

# Trace, compile and run project that uses Faster-RCNN
cd test/tracing/frcnn
mkdir build

# Trace model
python trace_model.py
cp fasterrcnn_resnet50_fpn.pt build

cd build
cmake .. -DTorch_DIR=$TORCH_PATH/share/cmake/Torch -DWITH_CUDA=$CMAKE_USE_CUDA
if [[ "$OSTYPE" == "msys" ]]; then
    echo "Windows"
else
    make
fi

# Run traced program
./test_frcnn_tracing
