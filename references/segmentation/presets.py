from collections import defaultdict

import torch
import transforms as reference_transforms


def get_modules(use_v2):
    # We need a protected import to avoid the V2 warning in case just V1 is used
    if use_v2:
        import torchvision.datapoints
        import torchvision.transforms.v2

        return torchvision.transforms.v2, torchvision.datapoints
    else:
        return reference_transforms, None


class SegmentationPresetTrain:
    def __init__(
        self,
        *,
        base_size,
        crop_size,
        hflip_prob=0.5,
        mean=(0.485, 0.456, 0.406),
        std=(0.229, 0.224, 0.225),
        backend="pil",
        use_v2=False,
    ):
        T, datapoints = get_modules(use_v2)

        transforms = []
        backend = backend.lower()
        if backend == "datapoint":
            transforms.append(T.ToImageTensor())
        elif backend == "tensor":
            transforms.append(T.PILToTensor())
        elif backend != "pil":
            raise ValueError(f"backend can be 'datapoint', 'tensor' or 'pil', but got {backend}")

        transforms += [T.RandomResize(min_size=int(0.5 * base_size), max_size=int(2.0 * base_size))]

        if hflip_prob > 0:
            transforms += [T.RandomHorizontalFlip(hflip_prob)]

        # if use_v2:
        #     # We need a custom pad transform here, since the padding we want to perform here is fundamentally
        #     # different from the padding in `RandomCrop` if `pad_if_needed=True`.
        #     transforms += [reference_transforms.PadIfSmaller(crop_size, fill=defaultdict(lambda: 0, {datapoints.Mask: 255}))]

        transforms += [T.RandomCrop(crop_size)]

        if backend == "pil":
            transforms += [T.PILToTensor()]

        transforms += [
            T.ConvertImageDtype(torch.float),
            T.Normalize(mean=mean, std=std),
        ]

        self.transforms = T.Compose(transforms)

    def __call__(self, img, target):
        return self.transforms(img, target)


class SegmentationPresetEval:
    def __init__(
        self, *, base_size, mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225), backend="pil", use_v2=False
    ):
        T, _ = get_modules(use_v2)

        transforms = []
        backend = backend.lower()
        if backend == "tensor":
            transforms += [T.PILToTensor()]
        elif backend == "datapoint":
            transforms += [T.ToImageTensor()]
        elif backend != "pil":
            raise ValueError(f"backend can be 'datapoint', 'tensor' or 'pil', but got {backend}")

        transforms += [T.RandomResize(min_size=base_size, max_size=base_size)]

        if backend == "pil":
            # Note: we could just convert to pure tensors even in v2?
            transforms += [T.ToImageTensor() if use_v2 else T.PILToTensor()]

        transforms += [
            T.ConvertImageDtype(torch.float),
            T.Normalize(mean=mean, std=std),
        ]
        self.transforms = T.Compose(transforms)

    def __call__(self, img, target):
        return self.transforms(img, target)
