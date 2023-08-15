import math
from typing import List, Optional

import PIL.Image
import torch
from torch.nn.functional import conv2d, pad as torch_pad

from torchvision import datapoints
from torchvision.transforms._functional_tensor import _max_value
from torchvision.transforms.functional import pil_to_tensor, to_pil_image

from torchvision.utils import _log_api_usage_once

from ._utils import _get_kernel, _register_kernel_internal


def normalize(
    inpt: torch.Tensor,
    mean: List[float],
    std: List[float],
    inplace: bool = False,
) -> torch.Tensor:
    if torch.jit.is_scripting():
        return normalize_image_tensor(inpt, mean=mean, std=std, inplace=inplace)

    _log_api_usage_once(normalize)

    kernel = _get_kernel(normalize, type(inpt))
    return kernel(inpt, mean=mean, std=std, inplace=inplace)


@_register_kernel_internal(normalize, torch.Tensor)
@_register_kernel_internal(normalize, datapoints.Image)
def normalize_image_tensor(
    image: torch.Tensor, mean: List[float], std: List[float], inplace: bool = False
) -> torch.Tensor:
    if not image.is_floating_point():
        raise TypeError(f"Input tensor should be a float tensor. Got {image.dtype}.")

    if image.ndim < 3:
        raise ValueError(f"Expected tensor to be a tensor image of size (..., C, H, W). Got {image.shape}.")

    if isinstance(std, (tuple, list)):
        divzero = not all(std)
    elif isinstance(std, (int, float)):
        divzero = std == 0
    else:
        divzero = False
    if divzero:
        raise ValueError("std evaluated to zero, leading to division by zero.")

    dtype = image.dtype
    device = image.device
    mean = torch.as_tensor(mean, dtype=dtype, device=device)
    std = torch.as_tensor(std, dtype=dtype, device=device)
    if mean.ndim == 1:
        mean = mean.view(-1, 1, 1)
    if std.ndim == 1:
        std = std.view(-1, 1, 1)

    if inplace:
        image = image.sub_(mean)
    else:
        image = image.sub(mean)

    return image.div_(std)


@_register_kernel_internal(normalize, datapoints.Video)
def normalize_video(video: torch.Tensor, mean: List[float], std: List[float], inplace: bool = False) -> torch.Tensor:
    return normalize_image_tensor(video, mean, std, inplace=inplace)


def gaussian_blur(inpt: torch.Tensor, kernel_size: List[int], sigma: Optional[List[float]] = None) -> torch.Tensor:
    if torch.jit.is_scripting():
        return gaussian_blur_image_tensor(inpt, kernel_size=kernel_size, sigma=sigma)

    _log_api_usage_once(gaussian_blur)

    kernel = _get_kernel(gaussian_blur, type(inpt))
    return kernel(inpt, kernel_size=kernel_size, sigma=sigma)


def _get_gaussian_kernel1d(kernel_size: int, sigma: float, dtype: torch.dtype, device: torch.device) -> torch.Tensor:
    lim = (kernel_size - 1) / (2.0 * math.sqrt(2.0) * sigma)
    x = torch.linspace(-lim, lim, steps=kernel_size, dtype=dtype, device=device)
    kernel1d = torch.softmax(x.pow_(2).neg_(), dim=0)
    return kernel1d


def _get_gaussian_kernel2d(
    kernel_size: List[int], sigma: List[float], dtype: torch.dtype, device: torch.device
) -> torch.Tensor:
    kernel1d_x = _get_gaussian_kernel1d(kernel_size[0], sigma[0], dtype, device)
    kernel1d_y = _get_gaussian_kernel1d(kernel_size[1], sigma[1], dtype, device)
    kernel2d = kernel1d_y.unsqueeze(-1) * kernel1d_x
    return kernel2d


@_register_kernel_internal(gaussian_blur, torch.Tensor)
@_register_kernel_internal(gaussian_blur, datapoints.Image)
def gaussian_blur_image_tensor(
    image: torch.Tensor, kernel_size: List[int], sigma: Optional[List[float]] = None
) -> torch.Tensor:
    # TODO: consider deprecating integers from sigma on the future
    if isinstance(kernel_size, int):
        kernel_size = [kernel_size, kernel_size]
    elif len(kernel_size) != 2:
        raise ValueError(f"If kernel_size is a sequence its length should be 2. Got {len(kernel_size)}")
    for ksize in kernel_size:
        if ksize % 2 == 0 or ksize < 0:
            raise ValueError(f"kernel_size should have odd and positive integers. Got {kernel_size}")

    if sigma is None:
        sigma = [ksize * 0.15 + 0.35 for ksize in kernel_size]
    else:
        if isinstance(sigma, (list, tuple)):
            length = len(sigma)
            if length == 1:
                s = float(sigma[0])
                sigma = [s, s]
            elif length != 2:
                raise ValueError(f"If sigma is a sequence, its length should be 2. Got {length}")
        elif isinstance(sigma, (int, float)):
            s = float(sigma)
            sigma = [s, s]
        else:
            raise TypeError(f"sigma should be either float or sequence of floats. Got {type(sigma)}")
    for s in sigma:
        if s <= 0.0:
            raise ValueError(f"sigma should have positive values. Got {sigma}")

    if image.numel() == 0:
        return image

    dtype = image.dtype
    shape = image.shape
    ndim = image.ndim
    if ndim == 3:
        image = image.unsqueeze(dim=0)
    elif ndim > 4:
        image = image.reshape((-1,) + shape[-3:])

    fp = torch.is_floating_point(image)
    kernel = _get_gaussian_kernel2d(kernel_size, sigma, dtype=dtype if fp else torch.float32, device=image.device)
    kernel = kernel.expand(shape[-3], 1, kernel.shape[0], kernel.shape[1])

    output = image if fp else image.to(dtype=torch.float32)

    # padding = (left, right, top, bottom)
    padding = [kernel_size[0] // 2, kernel_size[0] // 2, kernel_size[1] // 2, kernel_size[1] // 2]
    output = torch_pad(output, padding, mode="reflect")
    output = conv2d(output, kernel, groups=shape[-3])

    if ndim == 3:
        output = output.squeeze(dim=0)
    elif ndim > 4:
        output = output.reshape(shape)

    if not fp:
        output = output.round_().to(dtype=dtype)

    return output


@_register_kernel_internal(gaussian_blur, PIL.Image.Image)
def _gaussian_blur_image_pil(
    image: PIL.Image.Image, kernel_size: List[int], sigma: Optional[List[float]] = None
) -> PIL.Image.Image:
    t_img = pil_to_tensor(image)
    output = gaussian_blur_image_tensor(t_img, kernel_size=kernel_size, sigma=sigma)
    return to_pil_image(output, mode=image.mode)


@_register_kernel_internal(gaussian_blur, datapoints.Video)
def gaussian_blur_video(
    video: torch.Tensor, kernel_size: List[int], sigma: Optional[List[float]] = None
) -> torch.Tensor:
    return gaussian_blur_image_tensor(video, kernel_size, sigma)


def to_dtype(inpt: torch.Tensor, dtype: torch.dtype = torch.float, scale: bool = False) -> torch.Tensor:
    if torch.jit.is_scripting():
        return to_dtype_image_tensor(inpt, dtype=dtype, scale=scale)

    _log_api_usage_once(to_dtype)

    kernel = _get_kernel(to_dtype, type(inpt))
    return kernel(inpt, dtype=dtype, scale=scale)


def _num_value_bits(dtype: torch.dtype) -> int:
    if dtype == torch.uint8:
        return 8
    elif dtype == torch.int8:
        return 7
    elif dtype == torch.int16:
        return 15
    elif dtype == torch.int32:
        return 31
    elif dtype == torch.int64:
        return 63
    else:
        raise TypeError(f"Number of value bits is only defined for integer dtypes, but got {dtype}.")


@_register_kernel_internal(to_dtype, torch.Tensor)
@_register_kernel_internal(to_dtype, datapoints.Image)
def to_dtype_image_tensor(image: torch.Tensor, dtype: torch.dtype = torch.float, scale: bool = False) -> torch.Tensor:

    if image.dtype == dtype:
        return image
    elif not scale:
        return image.to(dtype)

    float_input = image.is_floating_point()
    if torch.jit.is_scripting():
        # TODO: remove this branch as soon as `dtype.is_floating_point` is supported by JIT
        float_output = torch.tensor(0, dtype=dtype).is_floating_point()
    else:
        float_output = dtype.is_floating_point

    if float_input:
        # float to float
        if float_output:
            return image.to(dtype)

        # float to int
        if (image.dtype == torch.float32 and dtype in (torch.int32, torch.int64)) or (
            image.dtype == torch.float64 and dtype == torch.int64
        ):
            raise RuntimeError(f"The conversion from {image.dtype} to {dtype} cannot be performed safely.")

        # For data in the range `[0.0, 1.0]`, just multiplying by the maximum value of the integer range and converting
        # to the integer dtype  is not sufficient. For example, `torch.rand(...).mul(255).to(torch.uint8)` will only
        # be `255` if the input is exactly `1.0`. See https://github.com/pytorch/vision/pull/2078#issuecomment-612045321
        # for a detailed analysis.
        # To mitigate this, we could round before we convert to the integer dtype, but this is an extra operation.
        # Instead, we can also multiply by the maximum value plus something close to `1`. See
        # https://github.com/pytorch/vision/pull/2078#issuecomment-613524965 for details.
        eps = 1e-3
        max_value = float(_max_value(dtype))
        # We need to scale first since the conversion would otherwise turn the input range `[0.0, 1.0]` into the
        # discrete set `{0, 1}`.
        return image.mul(max_value + 1.0 - eps).to(dtype)
    else:
        # int to float
        if float_output:
            return image.to(dtype).mul_(1.0 / _max_value(image.dtype))

        # int to int
        num_value_bits_input = _num_value_bits(image.dtype)
        num_value_bits_output = _num_value_bits(dtype)

        if num_value_bits_input > num_value_bits_output:
            return image.bitwise_right_shift(num_value_bits_input - num_value_bits_output).to(dtype)
        else:
            return image.to(dtype).bitwise_left_shift_(num_value_bits_output - num_value_bits_input)


# We encourage users to use to_dtype() instead but we keep this for BC
def convert_image_dtype(image: torch.Tensor, dtype: torch.dtype = torch.float32) -> torch.Tensor:
    return to_dtype_image_tensor(image, dtype=dtype, scale=True)


@_register_kernel_internal(to_dtype, datapoints.Video)
def to_dtype_video(video: torch.Tensor, dtype: torch.dtype = torch.float, scale: bool = False) -> torch.Tensor:
    return to_dtype_image_tensor(video, dtype, scale=scale)


@_register_kernel_internal(to_dtype, datapoints.BoundingBoxes, datapoint_wrapper=False)
@_register_kernel_internal(to_dtype, datapoints.Mask, datapoint_wrapper=False)
def _to_dtype_tensor_dispatch(inpt: torch.Tensor, dtype: torch.dtype, scale: bool = False) -> torch.Tensor:
    # We don't need to unwrap and rewrap here, since Datapoint.to() preserves the type
    return inpt.to(dtype)
