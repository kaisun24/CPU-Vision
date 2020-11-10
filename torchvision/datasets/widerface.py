from PIL import Image
import os
from os.path import abspath, expanduser
import torch
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from .utils import download_file_from_google_drive, check_integrity, download_url, \
    extract_archive, verify_str_arg
from .vision import VisionDataset


class WIDERFace(VisionDataset):
    """`WIDERFace <http://shuoyang1213.me/WIDERFACE/>`_ Dataset.

    Citation:
    @inproceedings{yang2016wider,
        author    = "Yang, Shuo and Luo, Ping and Loy, Chen Change and Tang, Xiaoou",
        booktitle = "IEEE Conference on Computer Vision and Pattern Recognition (CVPR)",
        title     = "WIDER FACE: A Face Detection Benchmark",
        year      = "2016"}

    Args:
        root (string): Root directory where images and annotations are downloaded to.
            Expects the following folder structure if download=False:
                <root>
                    └── widerface
                        ├── wider_face_split.zip
                        ├── WIDER_train.zip
                        ├── WIDER_val.zip
                        └── WIDER_test.zip
        split (string): The dataset split to use. One of {``train``, ``val``, ``test``}.
            Defaults to ``train``.
        target_type (string): The type of target to use, can be one
            of {``raw``, ``bbox``, ``attr``.``""``}. Can also be a list to
            output a tuple with all specified target types.
            The targets represent:
                ``raw``  (torch.tensor shape=(10,) dtype=int): all annotations combined (bbox + attr)
                ``bbox`` (torch.tensor shape=(4,) dtype=int): bounding box (x, y, width, height)
                ``attr`` (torch.tensor shape=(6,) dtype=int): label values for attributes
                    that represent (blur, expression, illumination, occlusion, pose, invalid)
            Defaults to ``raw``. If empty, ``None`` will be returned as target.
        transform (callable, optional): A function/transform that  takes in a PIL image
            and returns a transformed version. E.g, ``transforms.RandomCrop``
        target_transform (callable, optional): A function/transform that takes in the
            target and transforms it.
        download (bool, optional): If true, downloads the dataset from the internet and
            puts it in root directory. If dataset is already downloaded, it is not
            downloaded again.
    """

    BASE_FOLDER = "widerface"
    FILE_LIST = [
        # File ID                        MD5 Hash                            Filename
        ("0B6eKvaijfFUDQUUwd21EckhUbWs", "3fedf70df600953d25982bcd13d91ba2", "WIDER_train.zip"),
        ("0B6eKvaijfFUDd3dIRmpvSk8tLUk", "dfa7d7e790efa35df3788964cf0bbaea", "WIDER_val.zip"),
        ("0B6eKvaijfFUDbW4tdGpaYjgzZkU", "e5d8f4248ed24c334bbd12f49c29dd40", "WIDER_test.zip")
    ]
    ANNOTATIONS_FILE = ("http://mmlab.ie.cuhk.edu.hk/projects/WIDERFace/support/bbx_annotation/wider_face_split.zip",
                        "0e3767bcf0e326556d407bf5bff5d27c",
                        "wider_face_split.zip")

    def __init__(
            self,
            root: str,
            split: str = "train",
            target_type: Union[List[str], str] = "raw",
            transform: Optional[Callable] = None,
            target_transform: Optional[Callable] = None,
            download: bool = False,
    ) -> None:
        super(WIDERFace, self).__init__(root=os.path.join(root, self.BASE_FOLDER),
                                        transform=transform,
                                        target_transform=target_transform)
        # check arguments
        self.split = verify_str_arg(split, "split", ("train", "val", "test"))
        if self.split == "test":
            target_type = ""

        if isinstance(target_type, list):
            self.target_type = target_type
        else:
            self.target_type = [target_type]
        self.target_type = [verify_str_arg(t, "target_type", ("raw", "bbox", "attr", ""))
                            for t in self.target_type]

        if not self.target_type and self.target_transform is not None:
            raise RuntimeError('target_transform is specified but target_type is empty')

        if download:
            self.download()

        if not self._check_integrity():
            raise RuntimeError("Dataset not found or corrupted. " +
                               "You can use download=True to download it")

        # process dataset
        # dataset will be stored as a list of dict objects (img_info)
        self.img_info: Any = []
        if self.split in ("train", "val"):
            self.parse_train_val_annotations_file()
        else:
            self.parse_test_annotations_file()

    def __getitem__(self, index: int) -> Tuple[Any, Any]:
        """
        Args:
            index (int): Index

        Returns:
            tuple: (image, target) where target=None for the test split.
        """

        # stay consistent with other datasets and return a PIL Image
        img = Image.open(self.img_info[index]["img_path"])

        if self.transform is not None:
            img = self.transform(img)

        # prepare target
        target: Any = []
        for t in self.target_type:
            if t == "raw":
                target.append(self.img_info[index][t])
            elif t == "bbox":
                # bbox coordinates are the first 4 values in the raw annotation
                target.append(self.img_info[index]["raw"][:, :4])
            elif t == "attr":
                # attributes are defined after the bbox coordinates
                target.append(self.img_info[index]["raw"][:, 4:])
            else:  # target_type == "":
                target = None
                break
        if target:
            target = tuple(target) if len(target) > 1 else target[0]
            if self.target_transform is not None:
                target = self.target_transform(target)

        return img, target

    def __len__(self) -> int:
        return len(self.img_info)

    def extra_repr(self) -> str:
        lines = ["Target type: {target_type}", "Split: {split}"]
        return '\n'.join(lines).format(**self.__dict__)

    def parse_train_val_annotations_file(self) -> None:
        filename = "wider_face_train_bbx_gt.txt" if self.split == "train" else "wider_face_val_bbx_gt.txt"
        filepath = os.path.join(self.root, "wider_face_split", filename)

        with open(filepath, "r") as f:
            lines = f.readlines()

            file_name_line, num_boxes_line, box_annotation_line = True, False, False
            num_boxes, box_counter = 0, 0
            labels = []
            for line in lines:
                line = line.rstrip()
                if file_name_line:
                    img_path = os.path.join(self.root, "WIDER_" + self.split, "images", line)
                    img_path = abspath(expanduser(img_path))
                    file_name_line = False
                    num_boxes_line = True
                elif num_boxes_line:
                    num_boxes = int(line)
                    num_boxes_line = False
                    box_annotation_line = True
                elif box_annotation_line:
                    box_counter += 1
                    line_split = line.split(" ")
                    line_values = [int(x) for x in line_split]
                    labels.append(line_values)
                    if box_counter >= num_boxes:
                        box_annotation_line = False
                        file_name_line = True
                        self.img_info.append({
                            "img_path": img_path,
                            "raw": torch.tensor(labels),
                        })
                        box_counter = 0
                        labels.clear()
                else:
                    raise RuntimeError("Error parsing annotation file {}".format(filepath))

    def parse_test_annotations_file(self) -> None:
        filepath = os.path.join(self.root, "wider_face_split", "wider_face_test_filelist.txt")
        filepath = abspath(expanduser(filepath))
        with open(filepath, "r") as f:
            lines = f.readlines()
            for line in lines:
                line = line.rstrip()
                img_path = os.path.join(self.root, "WIDER_test", "images", line)
                img_path = abspath(expanduser(img_path))
                self.img_info.append({"img_path": img_path})

    def _check_integrity(self) -> bool:
        # Allow original archive to be deleted (zip). Only need the extracted images
        all_files = self.FILE_LIST.copy()
        all_files.append(self.ANNOTATIONS_FILE)
        for (_, md5, filename) in all_files:
            file, ext = os.path.splitext(filename)
            extracted_dir = os.path.join(self.root, file)
            if os.path.exists(extracted_dir):
                continue
            filepath = os.path.join(self.root, filename)
            if not check_integrity(filepath, md5):
                return False
            extract_archive(filepath)
        return True

    def download(self) -> None:
        if self._check_integrity():
            print('Files already downloaded and verified')
            return

        # download data if the extracted data doesn't exist
        for (file_id, md5, filename) in self.FILE_LIST:
            file, _ = os.path.splitext(filename)
            extracted_dir = os.path.join(self.root, file)
            if os.path.isdir(extracted_dir):
                continue
            download_file_from_google_drive(file_id, self.root, filename, md5)

        # download annotation files
        extracted_dir, _ = os.path.splitext(self.ANNOTATIONS_FILE[2])
        if not os.path.isdir(extracted_dir):
            download_url(url=self.ANNOTATIONS_FILE[0], root=self.root, md5=self.ANNOTATIONS_FILE[1])
