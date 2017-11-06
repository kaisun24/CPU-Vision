from __future__ import print_function
from PIL import Image
from functools import reduce
import os
import torch.utils.data as data
from .utils import download_url, check_integrity, list_dir, list_files


class Omniglot(data.Dataset):
    """`Omniglot <https://github.com/brendenlake/omniglot>`_ Dataset.
    Args:
        root (string): Root directory of dataset where directory
            ``omniglot-py`` exists.
        background (bool, optional): If True, creates dataset from the "background" set, otherwise
            creates from the "evaluation" set. This terminology is defined by the authors.
        transform (callable, optional): A function/transform that  takes in an PIL image
            and returns a transformed version. E.g, ``transforms.RandomCrop``
        target_transform (callable, optional): A function/transform that takes in the
            target and transforms it.
        download (bool, optional): If true, downloads the dataset zip files from the internet and
            puts it in root directory. If the zip files are already downloaded, they are not
            downloaded again.
        force_extract (bool, optional): If true, extracts the downloaded zip file irrespective
            of the existence of an extracted folder with the same name
    """
    folder = 'omniglot-py'
    download_url_prefix = 'https://github.com/brendenlake/omniglot/raw/master/python'
    zips_md5 = [
        ['images_background', '68d2efa1b9178cc56df9314c21c6e718'],
        ['images_evaluation', '6b91aef0f799c5bb55b94e3f2daec811'],
        # Kept for provisional purposes
        ['images_background_small1', 'e704a628b5459e08445c13499850abc4'],
        ['images_background_small2', 'b75a71a51d3b13f821f212756fe481fd'],
    ]

    def __init__(self, root, background=True,
                 transform=None, target_transform=None,
                 download=False,
                 force_extract=False):
        self.root = os.path.join(os.path.expanduser(root), self.folder)
        self.background = background
        self.transform = transform
        self.target_transform = target_transform

        if download:
            self.download(force_extract)

        if not self._check_integrity():
            raise RuntimeError('Dataset not found or corrupted.' +
                               ' You can use download=True to download it')

        self.target_folder = os.path.join(self.root, self._get_target_folder())
        self.alphabets_ = list_dir(self.target_folder)
        self.characters_ = list(reduce(lambda x, y: x + y,
           [
               [
                   os.path.join(alphabet, character)
                   for character in
                   list_dir(os.path.join(self.target_folder, alphabet))
               ]
               for alphabet in self.alphabets_
           ]
        ))
        self.character_images_ = [
            [
                tuple([image, idx])
                for image in list_files(os.path.join(self.target_folder, character), '.png')
            ]
            for idx, character in enumerate(self.characters_)
        ]
        self.flat_character_images_ = list(reduce(lambda x, y: x + y, self.character_images_))

    def __len__(self):
        return len(self.flat_character_images_)

    def __getitem__(self, index):
        """
        Args:
            index (int): Index

        Returns:
            tuple: (image, target) where target is index of the target character class.
        """
        image_name, character_class = self.flat_character_images_[index]
        image_path = os.path.join(self.target_folder, self.characters_[character_class], image_name)
        image = Image.open(image_path, mode='r').convert('L')

        if self.transform:
            image = self.transform(image)

        if self.target_transform:
            character_class = self.target_transform(character_class)

        return image, character_class

    def _check_integrity(self):
        for fzip in self.zips_md5:
            filename, md5 = fzip[0] + '.zip', fzip[1]
            fpath = os.path.join(self.root, filename)
            if not check_integrity(fpath, md5):
                return False
        return True

    def download(self, force_extract=False):
        import zipfile

        if self._check_integrity():
            print('Files already downloaded and verified')
            return

        for fzip in self.zips_md5:
            filename, md5 = fzip[0], fzip[1]
            zip_filename = filename + '.zip'
            url = self.download_url_prefix + '/' + zip_filename
            download_url(url, self.root, zip_filename, md5)

            if not os.path.isdir(os.path.join(self.root, filename)) or force_extract is True:
                print('Extracting downloaded file: ' + os.path.join(self.root, zip_filename))
                with zipfile.ZipFile(os.path.join(self.root, zip_filename), 'r') as zip_file:
                    zip_file.extractall(self.root)

    def _get_target_folder(self):
        return 'images_background' if self.background is True else 'images_evaluation'
