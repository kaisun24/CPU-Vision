import os
from typing import Any

from .folder import ImageFolder
from .utils import download_and_extract_archive, check_integrity


class EuroSAT(ImageFolder):
    """RGB version of the `EuroSAT <https://arxiv.org/pdf/1709.00029.pdf>`_ Dataset.

    Args:
        root (string): Root directory of dataset where ``EuroSAT.zip`` exists.
        download (bool, optional): If True, downloads the dataset from the internet and
            puts it in root directory. If dataset is already downloaded, it is not
            downloaded again.
        transform (callable, optional): A function/transform that  takes in an PIL image
            and returns a transformed version. E.g, ``transforms.RandomCrop``
        target_transform (callable, optional): A function/transform that takes in the
            target and transforms it.
    """

    url = "https://madm.dfki.de/files/sentinel/EuroSAT.zip"
    md5 = "c8fa014336c82ac7804f0398fcb19387"

    _class_map = {
        "AnnualCrop": "Annual Crop",
        "HerbaceousVegetation": "Herbaceous Vegetation",
        "Industrial": "Industrial Buildings",
        "PermanentCrop": "Permanent Crop",
        "Residential": "Residential Buildings",
        "SeaLake": "Sea & Lake",
    }

    def __init__(
        self,
        root: str,
        download: bool = False,
        **kwargs: Any,
    ) -> None:
        self.root = os.path.expanduser(root)

        if download:
            self.download()

        if not self._check_exists():
            raise RuntimeError("Dataset not found. You can use download=True to download it")

        super().__init__(self._data_folder, **kwargs)
        self.classes = [self._class_map.get(cls, cls) for cls in self.classes]
        self.root = os.path.expanduser(root)

    def __len__(self) -> int:
        return len(self.samples)

    @property
    def _base_folder(self) -> str:
        return os.path.join(self.root, self.__class__.__name__.lower())

    @property
    def _data_folder(self) -> str:
        return os.path.join(self._base_folder, "2750")

    def _check_exists(self) -> bool:
        return os.path.exists(self._data_folder)

    def download(self) -> None:

        if self._check_exists():
            return

        os.makedirs(self._base_folder, exist_ok=True)
        download_and_extract_archive(self.url, download_root=self._base_folder, md5=self.md5)
