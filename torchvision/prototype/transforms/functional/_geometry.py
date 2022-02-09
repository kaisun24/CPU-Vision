from typing import List, Optional, TypeVar

import torch
from torchvision.prototype import features
from torchvision.prototype.transforms import kernels as K
from torchvision.transforms import functional as _F, InterpolationMode

from ._utils import dispatch

T = TypeVar("T", bound=features.Feature)


def _horizontal_flip_bounding_box(input: features.BoundingBox) -> torch.Tensor:
    return K.horizontal_flip_bounding_box(input, format=input.format, image_size=input.image_size)


@dispatch(
    {
        features.Image: K.horizontal_flip_image,
        features.BoundingBox: _horizontal_flip_bounding_box,
    },
    pil_kernel=_F.hflip,
)
def horizontal_flip(input: T) -> T:
    """ADDME"""
    pass


def _resize_bounding_box(input: features.BoundingBox, *, size: List[int]) -> features.BoundingBox:
    output = K.resize_bounding_box(input, old_image_size=list(input.image_size), new_image_size=size)
    return features.BoundingBox.new_like(input, output, image_size=size)


@dispatch(
    {
        features.Image: K.resize_image,
        features.SegmentationMask: K.resize_segmentation_mask,
        features.BoundingBox: _resize_bounding_box,
    },
    pil_kernel=_F.resize,
)
def resize(
    input: T,
    *,
    size: List[int],
    interpolation: InterpolationMode,
    max_size: Optional[int],
    antialias: Optional[bool],
) -> T:
    """ADDME"""
    pass


@dispatch(
    {
        features.Image: K.center_crop_image,
    }
)
def center_crop(input: T, *, output_size: List[int]) -> T:
    """ADDME"""
    pass


@dispatch(
    {
        features.Image: K.resized_crop_image,
    }
)
def resized_crop(
    input: T,
    *,
    top: int,
    left: int,
    height: int,
    width: int,
    size: List[int],
    interpolation: InterpolationMode,
) -> T:
    """ADDME"""
    pass


@dispatch(
    {
        features.Image: K.affine_image,
    }
)
def affine(
    input: T,
    *,
    angle: float,
    translate: List[int],
    scale: float,
    shear: List[float],
    interpolation: InterpolationMode,
    fill: Optional[List[float]],
    resample: Optional[int],
    fillcolor: Optional[List[float]],
    center: Optional[List[int]],
) -> T:
    """ADDME"""
    pass


@dispatch(
    {
        features.Image: K.rotate_image,
    }
)
def rotate(
    input: T,
    *,
    angle: float,
    interpolation: InterpolationMode,
    expand: bool,
    center: Optional[List[int]],
    fill: Optional[List[float]],
    resample: Optional[int],
) -> T:
    """ADDME"""
    pass
