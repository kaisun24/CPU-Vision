import io
from typing import Any, Callable, Dict, List, Optional, Tuple

import torch
from torchdata.datapipes.iter import (
    IterDataPipe,
    Mapper,
    Shuffler,
    CSVParser,
)
from torchvision.prototype.datasets.decoder import raw
from torchvision.prototype.datasets.utils import (
    Dataset,
    DatasetConfig,
    DatasetInfo,
    HttpResource,
    OnlineResource,
    DatasetType,
)
from torchvision.prototype.datasets.utils._internal import INFINITE_BUFFER_SIZE, image_buffer_from_array
from torchvision.prototype.features import Label, Image


class SEMEION(Dataset):
    def _make_info(self) -> DatasetInfo:
        return DatasetInfo(
            "semeion",
            type=DatasetType.RAW,
            categories=10,
            homepage="https://archive.ics.uci.edu/ml/datasets/Semeion+Handwritten+Digit",
        )

    def resources(self, config: DatasetConfig) -> List[OnlineResource]:
        archive = HttpResource(
            "http://archive.ics.uci.edu/ml/machine-learning-databases/semeion/semeion.data",
            sha256="f43228ae3da5ea6a3c95069d53450b86166770e3b719dcc333182128fe08d4b1",
        )
        return [archive]

    def _collate_and_decode_sample(
        self,
        data: Tuple[str, ...],
        *,
        decoder: Optional[Callable[[io.IOBase], Dict[str, Any]]],
    ) -> Dict[str, Any]:
        image_data = torch.tensor([float(pixel) for pixel in data[:256]], dtype=torch.uint8).reshape(16, 16)
        label_data = [int(label) for label in data[256:] if label]

        category_idx = next((idx for idx, one_hot_label in enumerate(label_data) if one_hot_label))
        sample: Dict[str, Any] = dict(label=Label(category_idx, category=self.info.categories[category_idx]))

        if decoder is raw:
            sample["image"] = Image(image_data)
        else:
            buffer = image_buffer_from_array(image_data.numpy())
            sample.update(decoder(buffer) if decoder else dict(buffer=buffer))

        return sample

    def _make_datapipe(
        self,
        resource_dps: List[IterDataPipe],
        *,
        config: DatasetConfig,
        decoder: Optional[Callable[[io.IOBase], Dict[str, Any]]],
    ) -> IterDataPipe[Dict[str, Any]]:
        dp = resource_dps[0]
        dp = CSVParser(dp, delimiter=" ")
        dp = Shuffler(dp, buffer_size=INFINITE_BUFFER_SIZE)
        dp = Mapper(dp, self._collate_and_decode_sample, fn_kwargs=dict(decoder=decoder))
        return dp
