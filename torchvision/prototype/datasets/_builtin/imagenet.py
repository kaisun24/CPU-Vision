import functools
import io
import pathlib
import re
from typing import Any, Callable, Dict, List, Optional, Tuple, cast

import torch
from torchdata.datapipes.iter import IterDataPipe, LineReader, IterKeyZipper, Mapper, TarArchiveReader, Filter
from torchvision.prototype.datasets.utils import (
    Dataset,
    DatasetConfig,
    DatasetOption,
    OnlineResource,
    ManualDownloadResource,
    DatasetType,
)
from torchvision.prototype.datasets.utils._internal import (
    INFINITE_BUFFER_SIZE,
    BUILTIN_DIR,
    path_comparator,
    Enumerator,
    getitem,
    read_mat,
    hint_sharding,
    hint_shuffling,
)
from torchvision.prototype.features import Label


class ImageNetResource(ManualDownloadResource):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__("Register on https://image-net.org/ and follow the instructions there.", **kwargs)


class ImageNet(Dataset):
    def __init__(self):
        name = "imagenet"
        categories, wnids = zip(*self.read_categories_file(BUILTIN_DIR / f"{name}.categories"))
        super().__init__(
            name,
            DatasetOption("split", ("train", "val", "test")),
            type=DatasetType.IMAGE,
            description="""
            The ImageNet dataset contains 14,197,122 annotated images according to the WordNet hierarchy. Since 2010
            the dataset is used in the ImageNet Large Scale Visual Recognition Challenge (ILSVRC), a benchmark in image
            classification and object detection. The publicly released dataset contains a set of manually annotated
            training images. A set of test images is also released, with the manual annotations withheld. ILSVRC
            annotations fall into one of two categories: (1) image-level annotation of a binary label for the presence
            or absence of an object class in the image, e.g., "there are cars in this image" but "there are no tigers,"
            and (2) object-level annotation of a tight bounding box and class label around an object instance in the
            image, e.g., "there is a screwdriver centered at position (20,25) with width of 50 pixels and height of
            30 pixels". The ImageNet project does not own the copyright of the images, therefore only thumbnails and
            URLs of images are provided.

            - Total number of non-empty WordNet synsets: 21841
            - Total number of images: 14197122
            - Number of images with bounding box annotations: 1,034,908
            - Number of synsets with SIFT features: 1000
            - Number of images with SIFT features: 1.2 million
            """,
            dependencies=("scipy",),
            categories=categories,
            homepage="https://www.image-net.org/",
            attributes=dict(
                wnid_to_category="Mapping for WordNet IDs to human readable categories.",
                category_to_wnid="Mapping for human readable categories to WordNet IDs.",
            ),
        )
        # TODO: handle num_samples
        # sizes = FrozenMapping(
        #     [
        #         (DatasetConfig(split="train"), 1_281_167),
        #         (DatasetConfig(split="val"), 50_000),
        #         (DatasetConfig(split="test"), 100_000),
        #     ]
        # ),
        self.wnid_to_category = dict(zip(wnids, categories))
        self.category_to_wnid = dict(zip(categories, wnids))

    def supports_sharded(self) -> bool:
        return True

    _IMAGES_CHECKSUMS = {
        "train": "b08200a27a8e34218a0e58fde36b0fe8f73bc377f4acea2d91602057c3ca45bb",
        "val": "c7e06a6c0baccf06d8dbeb6577d71efff84673a5dbdd50633ab44f8ea0456ae0",
        "test_v10102019": "9cf7f8249639510f17d3d8a0deb47cd22a435886ba8e29e2b3223e65a4079eb4",
    }

    def resources(self, config: DatasetConfig) -> List[OnlineResource]:
        name = "test_v10102019" if config.split == "test" else config.split
        images = ImageNetResource(file_name=f"ILSVRC2012_img_{name}.tar", sha256=self._IMAGES_CHECKSUMS[name])

        devkit = ImageNetResource(
            file_name="ILSVRC2012_devkit_t12.tar.gz",
            sha256="b59243268c0d266621fd587d2018f69e906fb22875aca0e295b48cafaa927953",
        )

        return [images, devkit]

    _TRAIN_IMAGE_NAME_PATTERN = re.compile(r"(?P<wnid>n\d{8})_\d+[.]JPEG")

    def _collate_train_data(self, data: Tuple[str, io.IOBase]) -> Tuple[Tuple[Label, str, str], Tuple[str, io.IOBase]]:
        path = pathlib.Path(data[0])
        wnid = self._TRAIN_IMAGE_NAME_PATTERN.match(path.name).group("wnid")  # type: ignore[union-attr]
        category = self.wnid_to_category[wnid]
        label_data = (Label(self.categories.index(category)), category, wnid)
        return label_data, data

    _VAL_TEST_IMAGE_NAME_PATTERN = re.compile(r"ILSVRC2012_(val|test)_(?P<id>\d{8})[.]JPEG")

    def _val_test_image_key(self, data: Tuple[str, Any]) -> int:
        path = pathlib.Path(data[0])
        return int(self._VAL_TEST_IMAGE_NAME_PATTERN.match(path.name).group("id"))  # type: ignore[union-attr]

    def _collate_val_data(
        self, data: Tuple[Tuple[int, int], Tuple[str, io.IOBase]]
    ) -> Tuple[Tuple[Label, str, str], Tuple[str, io.IOBase]]:
        label_data, image_data = data
        _, label = label_data
        category = self.categories[label]
        wnid = self.category_to_wnid[category]
        return (Label(label), category, wnid), image_data

    def _collate_test_data(self, data: Tuple[str, io.IOBase]) -> Tuple[None, Tuple[str, io.IOBase]]:
        return None, data

    def _collate_and_decode_sample(
        self,
        data: Tuple[Optional[Tuple[Label, str, str]], Tuple[str, io.IOBase]],
        *,
        decoder: Optional[Callable[[io.IOBase], torch.Tensor]],
    ) -> Dict[str, Any]:
        label_data, (path, buffer) = data

        sample = dict(
            path=path,
            image=decoder(buffer) if decoder else buffer,
        )
        if label_data:
            sample.update(dict(zip(("label", "category", "wnid"), label_data)))

        return sample

    def _make_datapipe(
        self,
        resource_dps: List[IterDataPipe],
        *,
        config: DatasetConfig,
        decoder: Optional[Callable[[io.IOBase], torch.Tensor]],
    ) -> IterDataPipe[Dict[str, Any]]:
        images_dp, devkit_dp = resource_dps

        if config.split == "train":
            # the train archive is a tar of tars
            dp = TarArchiveReader(images_dp)
            dp = hint_sharding(dp)
            dp = hint_shuffling(dp)
            dp = Mapper(dp, self._collate_train_data)
        elif config.split == "val":
            devkit_dp = Filter(devkit_dp, path_comparator("name", "ILSVRC2012_validation_ground_truth.txt"))
            devkit_dp = LineReader(devkit_dp, return_path=False)
            devkit_dp = Mapper(devkit_dp, int)
            devkit_dp = Enumerator(devkit_dp, 1)
            devkit_dp = hint_sharding(devkit_dp)
            devkit_dp = hint_shuffling(devkit_dp)

            dp = IterKeyZipper(
                devkit_dp,
                images_dp,
                key_fn=getitem(0),
                ref_key_fn=self._val_test_image_key,
                buffer_size=INFINITE_BUFFER_SIZE,
            )
            dp = Mapper(dp, self._collate_val_data)
        else:  # config.split == "test"
            dp = hint_sharding(images_dp)
            dp = hint_shuffling(dp)
            dp = Mapper(dp, self._collate_test_data)

        return Mapper(dp, functools.partial(self._collate_and_decode_sample, decoder=decoder))

    # Although the WordNet IDs (wnids) are unique, the corresponding categories are not. For example, both n02012849
    # and n03126707 are labeled 'crane' while the first means the bird and the latter means the construction equipment
    _WNID_MAP = {
        "n03126707": "construction crane",
        "n03710721": "tank suit",
    }

    def _generate_categories(self, root: pathlib.Path) -> List[Tuple[str, ...]]:
        resources = self.resources(self.default_config)

        devkit_dp = resources[1].load(root)
        devkit_dp = Filter(devkit_dp, path_comparator("name", "meta.mat"))

        meta = next(iter(devkit_dp))[1]
        synsets = read_mat(meta, squeeze_me=True)["synsets"]
        categories_and_wnids = cast(
            List[Tuple[str, ...]],
            [
                (self._WNID_MAP.get(wnid, category.split(",", 1)[0]), wnid)
                for _, wnid, category, _, num_children, *_ in synsets
                # if num_children > 0, we are looking at a superclass that has no direct instance
                if num_children == 0
            ],
        )
        categories_and_wnids.sort(key=lambda category_and_wnid: category_and_wnid[1])

        return categories_and_wnids
