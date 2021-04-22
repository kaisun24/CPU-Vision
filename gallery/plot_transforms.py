"""
==========================
Illustration of transforms
==========================

This example illustrates the various transforms available in :mod:`torchvision.transforms`.
"""

from PIL import Image
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

import torchvision.transforms as T


orig_img = Image.open(Path('assets') / 'astronaut.jpg')


def plot(img, title: str = "", with_orig: bool = True, **kwargs):
    def _plot(img, title, **kwargs):
        plt.figure().suptitle(title, fontsize=25)
        plt.imshow(np.asarray(img), **kwargs)
        plt.axis('off')

    if with_orig:
        _plot(orig_img, "Original image")
    _plot(img, title, **kwargs)


####################################
# Pad
# ---
# The :class:`~torchvision.transforms.Pad` transform
# (see also :func:`~torchvision.transforms.functional.pad`)
# fills image borders with some pixel values.
padded_img = T.Pad(padding=30)(orig_img)
plot(padded_img, "Padded image")

####################################
# Resize
# ------
# The :class:`~torchvision.transforms.Resize` transform
# (see also :func:`~torchvision.transforms.functional.resize`)
# resizes an image.
resized_img = T.Resize(size=30)(orig_img)
plot(resized_img, "Resized image")

####################################
# CenterCrop
# ----------
# The :class:`~torchvision.transforms.CenterCrop` transform
# (see also :func:`~torchvision.transforms.functional.center_crop`)
# Crops the given image at the center.
center_cropped_img = T.CenterCrop(size=(100, 100))(orig_img)
plot(center_cropped_img, "Center Cropped Image")


####################################
# FiveCrop
# --------
# The :class:`~torchvision.transforms.FiveCrop` transform
# (see also :func:`~torchvision.transforms.functional.five_crop`)
# Crop the given image into four corners and the central crop.
(img1, img2, img3, img4, img5) = T.FiveCrop(size=(100, 100))(orig_img)
plot(img1, "Top Left Corner Image")
plot(img2, "Top Right Corner Image", with_orig=False)
plot(img3, "Bottom Left Corner Image", with_orig=False)
plot(img4, "Bottom Right Corner Image", with_orig=False)
plot(img5, "Center Image", with_orig=False)

####################################
# ColorJitter
# -----------
# The :class:`~torchvision.transforms.ColorJitter` transform
# randomly changes the brightness, saturation, and other properties of an image.
jitted_img = T.ColorJitter(brightness=.5, hue=.3)(orig_img)
plot(jitted_img, "Jitted image")

####################################
# Grayscale
# ---------
# The :class:`~torchvision.transforms.Grayscale` transform
# (see also :func:`~torchvision.transforms.functional.to_grayscale`)
# converts an image to grayscale
gray_img = T.Grayscale()(orig_img)
plot(gray_img, "Grayscale image", cmap='gray')

####################################
# RandomPerspective
# -----------------
# The :class:`~torchvision.transforms.RandomPerspective` transform
# (see also :func:`~torchvision.transforms.functional.perspective`)
# performs random perspective transform on an image.
perspectived_img = T.RandomPerspective(distortion_scale=0.6, p=1.0)(orig_img)
plot(perspectived_img, "Perspective transformed image")

####################################
# RandomRotation
# --------------
# The :class:`~torchvision.transforms.RandomRotation` transform
# (see also :func:`~torchvision.transforms.functional.rotate`)
# rotates an image with random angle.
rotated_img = T.RandomRotation(degrees=(30, 70))(orig_img)
plot(rotated_img, "Rotated image")

####################################
# RandomAffine
# ------------
# The :class:`~torchvision.transforms.RandomAffine` transform
# (see also :func:`~torchvision.transforms.functional.affine`)
# performs random affine transform on an image.
affined_img = T.RandomAffine(degrees=(30, 70), translate=(0.1, 0.3), scale=(0.5, 0.75))(orig_img)
plot(affined_img, "Affine transformed image")

####################################
# RandomCrop
# ----------
# The :class:`~torchvision.transforms.RandomCrop` transform
# (see also :func:`~torchvision.transforms.functional.crop`)
# crops an image at a random location.
crop = T.RandomCrop(size=(128, 128))(orig_img)
plot(crop, "Random crop")

####################################
# RandomResizedCrop
# -----------------
# The :class:`~torchvision.transforms.RandomResizedCrop` transform
# (see also :func:`~torchvision.transforms.functional.resized_crop`)
# crops an image at a random location, and then resizes the crop to a given
# size.
resized_crop = T.RandomResizedCrop(size=(32, 32))(orig_img)
plot(resized_crop, "Random resized crop")

####################################
# RandomHorizontalFlip
# --------------------
# The :class:`~torchvision.transforms.RandomHorizontalFlip` transform
# (see also :func:`~torchvision.transforms.functional.hflip`)
# performs horizontal flip of an image, with a given probability.
#
# .. note::
#   Since the transform is applied randomly, the two images below may actually be
#   the same.
random_hflip = T.RandomHorizontalFlip(p=0.5)(orig_img)
plot(random_hflip, "Random horizontal flip")

####################################
# RandomVerticalFlip
# ------------------
# The :class:`~torchvision.transforms.RandomVerticalFlip` transform
# (see also :func:`~torchvision.transforms.functional.vflip`)
# performs vertical flip of an image, with a given probability.
#
# .. note::
#   Since the transform is applied randomly, the two images below may actually be
#   the same.
random_vflip = T.RandomVerticalFlip(p=0.5)(orig_img)
plot(random_vflip, "Random vertical flip")

####################################
# RandomApply
# -----------
# The :class:`~torchvision.transforms.RandomApply` transform
# randomly applies a list of transforms, with a given probability
#
# .. note::
#   Since the transform is applied randomly, the two images below may actually be
#   the same.
random_apply = T.RandomApply(transforms=[T.RandomCrop(size=(64, 64))], p=0.5)(orig_img)
plot(random_apply, "Random Apply transform")

####################################
# GaussianBlur
# ------------
# The :class:`~torchvision.transforms.GaussianBlur` transform
# (see also :func:`~torchvision.transforms.functional.gaussian_blur`)
# performs gaussianblur transform on an image.
gaus_blur_img = T.GaussianBlur(kernel_size=(5, 9), sigma=(0.4, 3.0))(orig_img)
plot(gaus_blur_img, "Gaussian Blur of image")
