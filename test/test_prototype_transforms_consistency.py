import enum
import functools
import itertools

import numpy as np

import PIL.Image
import pytest

import torch
from test_prototype_transforms_functional import make_images
from torch.testing._comparison import assert_equal as _assert_equal, TensorLikePair
from torchvision import transforms as legacy_transforms
from torchvision._utils import sequence_to_str
from torchvision.prototype import features, transforms as prototype_transforms
from torchvision.prototype.transforms.functional import to_image_pil, to_image_tensor


class ImagePair(TensorLikePair):
    def _process_inputs(self, actual, expected, *, id, allow_subclasses):
        return super()._process_inputs(
            *[to_image_tensor(input) if isinstance(input, PIL.Image.Image) else input for input in [actual, expected]],
            id=id,
            allow_subclasses=allow_subclasses,
        )


assert_equal = functools.partial(_assert_equal, pair_types=[ImagePair], rtol=0, atol=0)


DEFAULT_MAKE_IMAGES_KWARGS = dict(color_spaces=[features.ColorSpace.RGB], extra_dims=[(4,)])


class ArgsKwargs:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __iter__(self):
        yield self.args
        yield self.kwargs

    def __str__(self):
        def short_repr(obj, max=20):
            repr_ = repr(obj)
            if len(repr_) <= max:
                return repr_

            return f"{repr_[:max//2]}...{repr_[-(max//2-3):]}"

        return ", ".join(
            itertools.chain(
                [short_repr(arg) for arg in self.args],
                [f"{param}={short_repr(kwarg)}" for param, kwarg in self.kwargs.items()],
            )
        )


class ConsistencyConfig:
    def __init__(
        self, prototype_cls, legacy_cls, transform_args_kwargs=None, make_images_kwargs=None, supports_pil=True
    ):
        self.prototype_cls = prototype_cls
        self.legacy_cls = legacy_cls
        self.transform_args_kwargs = transform_args_kwargs or [((), dict())]
        self.make_images_kwargs = make_images_kwargs or DEFAULT_MAKE_IMAGES_KWARGS
        self.supports_pil = supports_pil

    def parametrization(self):
        return [
            pytest.param(
                self.prototype_cls,
                self.legacy_cls,
                args_kwargs,
                self.make_images_kwargs,
                self.supports_pil,
                id=f"{self.legacy_cls.__name__}({args_kwargs})",
            )
            for args_kwargs in self.transform_args_kwargs
        ]


# These are here since both the prototype and legacy transform need to be constructed with the same random parameters
LINEAR_TRANSFORMATION_MEAN = torch.rand(36)
LINEAR_TRANSFORMATION_MATRIX = torch.rand([LINEAR_TRANSFORMATION_MEAN.numel()] * 2)

CONSISTENCY_CONFIGS = [
    ConsistencyConfig(
        prototype_transforms.Normalize,
        legacy_transforms.Normalize,
        [
            ArgsKwargs(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
        ],
        supports_pil=False,
        make_images_kwargs=dict(DEFAULT_MAKE_IMAGES_KWARGS, dtypes=[torch.float]),
    ),
    ConsistencyConfig(
        prototype_transforms.Resize,
        legacy_transforms.Resize,
        [
            ArgsKwargs(32),
            ArgsKwargs((32, 29)),
            ArgsKwargs((31, 28), interpolation=prototype_transforms.InterpolationMode.NEAREST),
            ArgsKwargs((33, 26), interpolation=prototype_transforms.InterpolationMode.BICUBIC),
            # FIXME: these are currently failing, since the new transform only supports the enum. The int input is
            #  already deprecated and scheduled to be removed in 0.15. Should we support ints on the prototype
            #  transform? I guess it depends if we roll out before 0.15 or not.
            # ArgsKwargs((30, 27), interpolation=0),
            # ArgsKwargs((35, 29), interpolation=2),
            # ArgsKwargs((34, 25), interpolation=3),
            ArgsKwargs(31, max_size=32),
            ArgsKwargs(30, max_size=100),
            ArgsKwargs((29, 32), antialias=False),
            ArgsKwargs((28, 31), antialias=True),
        ],
    ),
    ConsistencyConfig(
        prototype_transforms.CenterCrop,
        legacy_transforms.CenterCrop,
        [
            ArgsKwargs(18),
            ArgsKwargs((18, 13)),
        ],
    ),
    ConsistencyConfig(
        prototype_transforms.FiveCrop,
        legacy_transforms.FiveCrop,
        [
            ArgsKwargs(18),
            ArgsKwargs((18, 13)),
        ],
        make_images_kwargs=dict(DEFAULT_MAKE_IMAGES_KWARGS, sizes=[(20, 19)]),
    ),
    ConsistencyConfig(
        prototype_transforms.TenCrop,
        legacy_transforms.TenCrop,
        [
            ArgsKwargs(18),
            ArgsKwargs((18, 13)),
        ],
        make_images_kwargs=dict(DEFAULT_MAKE_IMAGES_KWARGS, sizes=[(20, 19)]),
    ),
    ConsistencyConfig(
        prototype_transforms.Pad,
        legacy_transforms.Pad,
        [
            ArgsKwargs(3),
            ArgsKwargs([3]),
            ArgsKwargs([2, 3]),
            ArgsKwargs([3, 2, 1, 4]),
            ArgsKwargs(5, fill=1, padding_mode="constant"),
            ArgsKwargs(5, padding_mode="edge"),
            ArgsKwargs(5, padding_mode="reflect"),
            ArgsKwargs(5, padding_mode="symmetric"),
        ],
    ),
    ConsistencyConfig(
        prototype_transforms.LinearTransformation,
        legacy_transforms.LinearTransformation,
        [
            ArgsKwargs(LINEAR_TRANSFORMATION_MATRIX, LINEAR_TRANSFORMATION_MEAN),
        ],
        # Make sure that the product of the height, width and number of channels matches the number of elements in
        # `LINEAR_TRANSFORMATION_MEAN`. For example 2 * 6 * 3 == 4 * 3 * 3 == 36.
        make_images_kwargs=dict(
            DEFAULT_MAKE_IMAGES_KWARGS, sizes=[(2, 6), (4, 3)], color_spaces=[features.ColorSpace.RGB]
        ),
        supports_pil=False,
    ),
    ConsistencyConfig(
        prototype_transforms.Grayscale,
        legacy_transforms.Grayscale,
        [
            ArgsKwargs(num_output_channels=1),
            ArgsKwargs(num_output_channels=3),
        ],
        make_images_kwargs=dict(
            DEFAULT_MAKE_IMAGES_KWARGS, color_spaces=[features.ColorSpace.RGB, features.ColorSpace.GRAY]
        ),
    ),
    ConsistencyConfig(
        prototype_transforms.ConvertImageDtype,
        legacy_transforms.ConvertImageDtype,
        [
            ArgsKwargs(torch.float16),
            ArgsKwargs(torch.bfloat16),
            ArgsKwargs(torch.float32),
            ArgsKwargs(torch.float64),
            ArgsKwargs(torch.uint8),
        ],
        supports_pil=False,
    ),
    ConsistencyConfig(
        prototype_transforms.ToPILImage,
        legacy_transforms.ToPILImage,
        [ArgsKwargs()],
        make_images_kwargs=dict(
            color_spaces=[
                features.ColorSpace.GRAY,
                features.ColorSpace.GRAY_ALPHA,
                features.ColorSpace.RGB,
                features.ColorSpace.RGB_ALPHA,
            ],
            extra_dims=[()],
        ),
        supports_pil=False,
    ),
    ConsistencyConfig(
        prototype_transforms.Lambda,
        legacy_transforms.Lambda,
        [
            ArgsKwargs(lambda image: image / 2),
        ],
        # Technically, this also supports PIL, but it is overkill to write a function here that supports tensor and PIL
        # images given that the transform does nothing but call it anyway.
        supports_pil=False,
    ),
]


def test_automatic_coverage_deterministic():
    legacy = {
        name
        for name, obj in legacy_transforms.__dict__.items()
        if not name.startswith("_")
        and isinstance(obj, type)
        and not issubclass(obj, enum.Enum)
        and name
        not in {
            "Compose",
            # This framework is based on the assumption that the input image can always be a tensor and optionally a
            # PIL image. The transforms below require a non-tensor input and thus have to be tested manually.
            "PILToTensor",
            "ToTensor",
        }
    }
    # filter out random transformations
    legacy = {name for name in legacy if "Random" not in name} - {
        "AugMix",
        "TrivialAugmentWide",
        "GaussianBlur",
        "RandAugment",
        "AutoAugment",
        "ColorJitter",
        "ElasticTransform",
    }

    prototype = {config.legacy_cls.__name__ for config in CONSISTENCY_CONFIGS}

    missing = legacy - prototype
    if missing:
        raise AssertionError(
            f"The prototype transformations {sequence_to_str(sorted(missing), separate_last='and ')} "
            f"are not checked for consistency although a legacy counterpart exists."
        )


@pytest.mark.parametrize(
    ("prototype_transform_cls", "legacy_transform_cls", "args_kwargs", "make_images_kwargs", "supports_pil"),
    itertools.chain.from_iterable(config.parametrization() for config in CONSISTENCY_CONFIGS),
)
def test_consistency(prototype_transform_cls, legacy_transform_cls, args_kwargs, make_images_kwargs, supports_pil):
    args, kwargs = args_kwargs

    try:
        legacy = legacy_transform_cls(*args, **kwargs)
    except Exception as exc:
        raise pytest.UsageError(
            f"Initializing the legacy transform failed with the error above. "
            f"Please correct the `ArgsKwargs({args_kwargs})` in the `ConsistencyConfig`."
        ) from exc

    try:
        prototype = prototype_transform_cls(*args, **kwargs)
    except Exception as exc:
        raise AssertionError(
            "Initializing the prototype transform failed with the error above. "
            "This means there is a consistency bug in the constructor."
        ) from exc

    for image in make_images(**make_images_kwargs):
        image_tensor = torch.Tensor(image)
        image_pil = to_image_pil(image) if image.ndim == 3 and supports_pil else None

        image_repr = f"[{tuple(image.shape)}, {str(image.dtype).rsplit('.')[-1]}]"

        try:
            output_legacy_tensor = legacy(image_tensor)
        except Exception as exc:
            raise pytest.UsageError(
                f"Transforming a tensor image {image_repr} failed in the legacy transform with the "
                f"error above. This means that you need to specify the parameters passed to `make_images` through the "
                "`make_images_kwargs` of the `ConsistencyConfig`."
            ) from exc

        try:
            output_prototype_tensor = prototype(image_tensor)
        except Exception as exc:
            raise AssertionError(
                f"Transforming a tensor image with shape {image_repr} failed in the prototype transform with "
                f"the error above. This means there is a consistency bug either in `_get_params` or in the "
                f"`is_simple_tensor` path in `_transform`."
            ) from exc

        assert_equal(
            output_prototype_tensor,
            output_legacy_tensor,
            msg=lambda msg: f"Tensor image consistency check failed with: \n\n{msg}",
        )

        try:
            output_prototype_image = prototype(image)
        except Exception as exc:
            raise AssertionError(
                f"Transforming a feature image with shape {image_repr} failed in the prototype transform with "
                f"the error above. This means there is a consistency bug either in `_get_params` or in the "
                f"`features.Image` path in `_transform`."
            ) from exc

        assert_equal(
            output_prototype_image,
            output_prototype_tensor,
            msg=lambda msg: f"Output for feature and tensor images is not equal: \n\n{msg}",
        )

        if image_pil is not None:
            try:
                output_legacy_pil = legacy(image_pil)
            except Exception as exc:
                raise pytest.UsageError(
                    f"Transforming a PIL image with shape {image_repr} failed in the legacy transform with the "
                    f"error above. If this transform does not support PIL images, set `supports_pil=False` on the "
                    "`ConsistencyConfig`. "
                ) from exc

            try:
                output_prototype_pil = prototype(image_pil)
            except Exception as exc:
                raise AssertionError(
                    f"Transforming a PIL image with shape {image_repr} failed in the prototype transform with "
                    f"the error above. This means there is a consistency bug either in `_get_params` or in the "
                    f"`PIL.Image.Image` path in `_transform`."
                ) from exc

            assert_equal(
                output_prototype_pil,
                output_legacy_pil,
                msg=lambda msg: f"PIL image consistency check failed with: \n\n{msg}",
            )


class TestToTensorTransforms:
    def test_pil_to_tensor(self):
        for image in make_images(extra_dims=[()]):
            image_pil = to_image_pil(image)

            prototype_transform = prototype_transforms.PILToTensor()
            legacy_transform = legacy_transforms.PILToTensor()

            assert_equal(prototype_transform(image_pil), legacy_transform(image_pil))

    def test_to_tensor(self):
        for image in make_images(extra_dims=[()]):
            image_pil = to_image_pil(image)
            image_numpy = np.array(image_pil)

            prototype_transform = prototype_transforms.ToTensor()
            legacy_transform = legacy_transforms.ToTensor()

            assert_equal(prototype_transform(image_pil), legacy_transform(image_pil))
            assert_equal(prototype_transform(image_numpy), legacy_transform(image_numpy))
