import re
import warnings
from functools import partial
from typing import Any, Optional, Tuple

import torch.nn as nn

from ...models.densenet import DenseNet
from ..transforms.presets import ImageNetEval
from ._api import Weights, WeightEntry
from ._meta import _IMAGENET_CATEGORIES


__all__ = [
    "DenseNet",
    "DenseNet121Weights",
    "DenseNet161Weights",
    "DenseNet169Weights",
    "DenseNet201Weights",
    "densenet121",
    "densenet161",
    "densenet169",
    "densenet201",
]


def _load_state_dict(model: nn.Module, weights: Weights, progress: bool) -> None:
    # '.'s are no longer allowed in module names, but previous _DenseLayer
    # has keys 'norm.1', 'relu.1', 'conv.1', 'norm.2', 'relu.2', 'conv.2'.
    # They are also in the checkpoints in model_urls. This pattern is used
    # to find such keys.
    pattern = re.compile(
        r"^(.*denselayer\d+\.(?:norm|relu|conv))\.((?:[12])\.(?:weight|bias|running_mean|running_var))$"
    )

    state_dict = weights.state_dict(progress=progress)
    for key in list(state_dict.keys()):
        res = pattern.match(key)
        if res:
            new_key = res.group(1) + res.group(2)
            state_dict[new_key] = state_dict[key]
            del state_dict[key]
    model.load_state_dict(state_dict)


def _densenet(
    growth_rate: int,
    block_config: Tuple[int, int, int, int],
    num_init_features: int,
    weights: Weights,
    progress: bool,
    **kwargs: Any,
) -> DenseNet:
    if weights is not None:
        kwargs["num_classes"] = len(weights.meta["categories"])

    model = DenseNet(growth_rate, block_config, num_init_features, **kwargs)

    if weights is not None:
        _load_state_dict(model=model, weights=weights, progress=progress)

    return model


_common_meta = {
    "size": (224, 224),
    "categories": _IMAGENET_CATEGORIES,
}


class DenseNet121Weights(Weights):
    ImageNet1K_RefV1 = WeightEntry(
        url="https://download.pytorch.org/models/densenet121-a639ec97.pth",
        transforms=partial(ImageNetEval, crop_size=224),
        meta={
            **_common_meta,
            "recipe": "",
            "acc@1": 74.434,
            "acc@5": 91.972,
        },
    )


class DenseNet161Weights(Weights):
    ImageNet1K_RefV1 = WeightEntry(
        url="https://download.pytorch.org/models/densenet161-8d451a50.pth",
        transforms=partial(ImageNetEval, crop_size=224),
        meta={
            **_common_meta,
            "recipe": "",
            "acc@1": 77.138,
            "acc@5": 93.560,
        },
    )


class DenseNet169Weights(Weights):
    ImageNet1K_RefV1 = WeightEntry(
        url="https://download.pytorch.org/models/densenet169-b2777c0a.pth",
        transforms=partial(ImageNetEval, crop_size=224),
        meta={
            **_common_meta,
            "recipe": "",
            "acc@1": 75.600,
            "acc@5": 92.806,
        },
    )


class DenseNet201Weights(Weights):
    ImageNet1K_RefV1 = WeightEntry(
        url="https://download.pytorch.org/models/densenet201-c1103571.pth",
        transforms=partial(ImageNetEval, crop_size=224),
        meta={
            **_common_meta,
            "recipe": "",
            "acc@1": 76.896,
            "acc@5": 93.370,
        },
    )


def densenet121(weights: Optional[DenseNet121Weights] = None, progress: bool = True, **kwargs: Any) -> DenseNet:
    if "pretrained" in kwargs:
        warnings.warn("The argument pretrained is deprecated, please use weights instead.")
        weights = DenseNet121Weights.ImageNet1K_RefV1 if kwargs.pop("pretrained") else None
    weights = DenseNet121Weights.verify(weights)

    return _densenet(32, (6, 12, 24, 16), 64, weights, progress, **kwargs)


def densenet161(weights: Optional[DenseNet161Weights] = None, progress: bool = True, **kwargs: Any) -> DenseNet:
    if "pretrained" in kwargs:
        warnings.warn("The argument pretrained is deprecated, please use weights instead.")
        weights = DenseNet161Weights.ImageNet1K_RefV1 if kwargs.pop("pretrained") else None
    weights = DenseNet161Weights.verify(weights)

    return _densenet(48, (6, 12, 36, 24), 96, weights, progress, **kwargs)


def densenet169(weights: Optional[DenseNet169Weights] = None, progress: bool = True, **kwargs: Any) -> DenseNet:
    if "pretrained" in kwargs:
        warnings.warn("The argument pretrained is deprecated, please use weights instead.")
        weights = DenseNet169Weights.ImageNet1K_RefV1 if kwargs.pop("pretrained") else None
    weights = DenseNet169Weights.verify(weights)

    return _densenet(32, (6, 12, 32, 32), 64, weights, progress, **kwargs)


def densenet201(weights: Optional[DenseNet201Weights] = None, progress: bool = True, **kwargs: Any) -> DenseNet:
    if "pretrained" in kwargs:
        warnings.warn("The argument pretrained is deprecated, please use weights instead.")
        weights = DenseNet201Weights.ImageNet1K_RefV1 if kwargs.pop("pretrained") else None
    weights = DenseNet201Weights.verify(weights)

    return _densenet(32, (6, 12, 48, 32), 64, weights, progress, **kwargs)
