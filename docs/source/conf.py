#!/usr/bin/env python3
#
# PyTorch documentation build configuration file, created by
# sphinx-quickstart on Fri Dec 23 13:31:47 2016.
#
# This file is execfile()d with the current directory set to its
# containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))

import os
import textwrap
from copy import copy
from pathlib import Path

import pytorch_sphinx_theme
import torchvision
import torchvision.models as M
from tabulate import tabulate


# -- General configuration ------------------------------------------------

# Required version of sphinx is set from docs/requirements.txt

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.doctest",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx.ext.mathjax",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.duration",
    "sphinx_gallery.gen_gallery",
    "sphinx_copybutton",
]

sphinx_gallery_conf = {
    "examples_dirs": "../../gallery/",  # path to your example scripts
    "gallery_dirs": "auto_examples",  # path to where to save gallery generated output
    "backreferences_dir": "gen_modules/backreferences",
    "doc_module": ("torchvision",),
}

napoleon_use_ivar = True
napoleon_numpy_docstring = False
napoleon_google_docstring = True


# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
source_suffix = {
    ".rst": "restructuredtext",
}

# The master toctree document.
master_doc = "index"

# General information about the project.
project = "Torchvision"
copyright = "2017-present, Torch Contributors"
author = "Torch Contributors"

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = "main (" + torchvision.__version__ + " )"
# The full version, including alpha/beta/rc tags.
release = "main"
VERSION = os.environ.get("VERSION", None)
if VERSION:
    # Turn 1.11.0aHASH into 1.11 (major.minor only)
    version = ".".join(version.split(".")[:2])
    html_title = " ".join((project, version, "documentation"))
    release = version


# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = None

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This patterns also effect to html_static_path and html_extra_path
exclude_patterns = []

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = True


# -- Options for HTML output ----------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "pytorch_sphinx_theme"
html_theme_path = [pytorch_sphinx_theme.get_html_theme_path()]

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#
html_theme_options = {
    "collapse_navigation": False,
    "display_version": True,
    "logo_only": True,
    "pytorch_project": "docs",
    "navigation_with_keys": True,
    "analytics_id": "UA-117752657-2",
}

html_logo = "_static/img/pytorch-logo-dark.svg"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# TODO: remove this once https://github.com/pytorch/pytorch_sphinx_theme/issues/125 is fixed
html_css_files = [
    "css/custom_torchvision.css",
]

# -- Options for HTMLHelp output ------------------------------------------

# Output file base name for HTML help builder.
htmlhelp_basename = "PyTorchdoc"


autosummary_generate = True


# -- Options for LaTeX output ---------------------------------------------
latex_elements = {
    # The paper size ('letterpaper' or 'a4paper').
    #
    # 'papersize': 'letterpaper',
    # The font size ('10pt', '11pt' or '12pt').
    #
    # 'pointsize': '10pt',
    # Additional stuff for the LaTeX preamble.
    #
    # 'preamble': '',
    # Latex figure (float) alignment
    #
    # 'figure_align': 'htbp',
}


# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
    (master_doc, "pytorch.tex", "torchvision Documentation", "Torch Contributors", "manual"),
]


# -- Options for manual page output ---------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [(master_doc, "torchvision", "torchvision Documentation", [author], 1)]


# -- Options for Texinfo output -------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (
        master_doc,
        "torchvision",
        "torchvision Documentation",
        author,
        "torchvision",
        "One line description of project.",
        "Miscellaneous",
    ),
]


# Example configuration for intersphinx: refer to the Python standard library.
intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "torch": ("https://pytorch.org/docs/stable/", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "PIL": ("https://pillow.readthedocs.io/en/stable/", None),
    "matplotlib": ("https://matplotlib.org/stable/", None),
}

# -- A patch that prevents Sphinx from cross-referencing ivar tags -------
# See http://stackoverflow.com/a/41184353/3343043

from docutils import nodes
from sphinx import addnodes
from sphinx.util.docfields import TypedField


def patched_make_field(self, types, domain, items, **kw):
    # `kw` catches `env=None` needed for newer sphinx while maintaining
    #  backwards compatibility when passed along further down!

    # type: (list, unicode, tuple) -> nodes.field  # noqa: F821
    def handle_item(fieldarg, content):
        par = nodes.paragraph()
        par += addnodes.literal_strong("", fieldarg)  # Patch: this line added
        # par.extend(self.make_xrefs(self.rolename, domain, fieldarg,
        #                           addnodes.literal_strong))
        if fieldarg in types:
            par += nodes.Text(" (")
            # NOTE: using .pop() here to prevent a single type node to be
            # inserted twice into the doctree, which leads to
            # inconsistencies later when references are resolved
            fieldtype = types.pop(fieldarg)
            if len(fieldtype) == 1 and isinstance(fieldtype[0], nodes.Text):
                typename = "".join(n.astext() for n in fieldtype)
                typename = typename.replace("int", "python:int")
                typename = typename.replace("long", "python:long")
                typename = typename.replace("float", "python:float")
                typename = typename.replace("type", "python:type")
                par.extend(self.make_xrefs(self.typerolename, domain, typename, addnodes.literal_emphasis, **kw))
            else:
                par += fieldtype
            par += nodes.Text(")")
        par += nodes.Text(" -- ")
        par += content
        return par

    fieldname = nodes.field_name("", self.label)
    if len(items) == 1 and self.can_collapse:
        fieldarg, content = items[0]
        bodynode = handle_item(fieldarg, content)
    else:
        bodynode = self.list_type()
        for fieldarg, content in items:
            bodynode += nodes.list_item("", handle_item(fieldarg, content))
    fieldbody = nodes.field_body("", bodynode)
    return nodes.field("", fieldname, fieldbody)


TypedField.make_field = patched_make_field


def inject_minigalleries(app, what, name, obj, options, lines):
    """Inject a minigallery into a docstring.

    This avoids having to manually write the .. minigallery directive for every item we want a minigallery for,
    as it would be easy to miss some.

    This callback is called after the .. auto directives (like ..autoclass) have been processed,
    and modifies the lines parameter inplace to add the .. minigallery that will show which examples
    are using which object.

    It's a bit hacky, but not *that* hacky when you consider that the recommended way is to do pretty much the same,
    but instead with templates using autosummary (which we don't want to use):
    (https://sphinx-gallery.github.io/stable/configuration.html#auto-documenting-your-api-with-links-to-examples)

    For docs on autodoc-process-docstring, see the autodoc docs:
    https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html
    """

    if what in ("class", "function"):
        lines.append(f".. minigallery:: {name}")
        lines.append(f"    :add-heading: Examples using ``{name.split('.')[-1]}``:")
        # avoid heading entirely to avoid warning. As a bonud it actually renders better
        lines.append("    :heading-level: 9")
        lines.append("\n")


def inject_weight_metadata(app, what, name, obj, options, lines):
    """This hook is used to generate docs for the models weights.

    Objects like ResNet18_Weights are enums with fields, where each field is a Weight object.
    Enums aren't easily documented in Python so the solution we're going for is to:

    - add an autoclass directive in the model's builder docstring, e.g.

    ```
    .. autoclass:: torchvision.models.ResNet34_Weights
        :members:
    ```

    (see resnet.py for an example)
    - then this hook is called automatically when building the docs, and it generates the text that gets
      used within the autoclass directive.
    """

    if obj.__name__.endswith(("_Weights", "_QuantizedWeights")):

        if len(obj) == 0:
            lines[:] = ["There are no available pre-trained weights."]
            return

        lines[:] = [
            "The model builder above accepts the following values as the ``weights`` parameter.",
            f"``{obj.__name__}.DEFAULT`` is equivalent to ``{obj.DEFAULT}``.",
        ]

        if obj.__doc__ != "An enumeration.":
            # We only show the custom enum doc if it was overriden. The default one from Python is "An enumeration"
            lines.append("")
            lines.append(obj.__doc__)

        lines.append("")

        for field in obj:
            lines += [f"**{str(field)}**:", ""]
            if field == obj.DEFAULT:
                lines += [f"This weight is also available as ``{obj.__name__}.DEFAULT``.", ""]

            table = []

            # the `meta` dict contains another embedded `metrics` dict. To
            # simplify the table generation below, we create the
            # `meta_with_metrics` dict, where the metrics dict has been "flattened"
            meta = copy(field.meta)
            metrics = meta.pop("metrics", {})
            meta_with_metrics = dict(meta, **metrics)

            # We don't want to document these, they can be too long
            for k in ["categories", "keypoint_names"]:
                meta_with_metrics.pop(k, None)

            custom_docs = meta_with_metrics.pop("_docs", None)  # Custom per-Weights docs
            if custom_docs is not None:
                lines += [custom_docs, ""]

            for k, v in meta_with_metrics.items():
                if k in {"recipe", "license"}:
                    v = f"`link <{v}>`__"
                elif k == "min_size":
                    v = f"height={v[0]}, width={v[1]}"
                table.append((str(k), str(v)))
            table = tabulate(table, tablefmt="rst")
            lines += [".. rst-class:: table-weights"]  # Custom CSS class, see custom_torchvision.css
            lines += [".. table::", ""]
            lines += textwrap.indent(table, " " * 4).split("\n")
            lines.append("")
            lines.append(
                f"The inference transforms are available at ``{str(field)}.transforms`` and "
                f"perform the following operations: {field.transforms().describe()}"
            )
            lines.append("")


def generate_weights_table(module, table_name, metrics, include_patterns=None, exclude_patterns=None):
    weights_endswith = "_QuantizedWeights" if module.__name__.split(".")[-1] == "quantization" else "_Weights"
    weight_enums = [getattr(module, name) for name in dir(module) if name.endswith(weights_endswith)]
    weights = [w for weight_enum in weight_enums for w in weight_enum]

    if include_patterns is not None:
        weights = [w for w in weights if any(p in str(w) for p in include_patterns)]
    if exclude_patterns is not None:
        weights = [w for w in weights if all(p not in str(w) for p in exclude_patterns)]

    metrics_keys, metrics_names = zip(*metrics)
    column_names = ["Weight"] + list(metrics_names) + ["Params", "Recipe"]
    column_names = [f"**{name}**" for name in column_names]  # Add bold

    content = [
        (
            f":class:`{w} <{type(w).__name__}>`",
            *(w.meta["metrics"][metric] for metric in metrics_keys),
            f"{w.meta['num_params']/1e6:.1f}M",
            f"`link <{w.meta['recipe']}>`__",
        )
        for w in weights
    ]
    table = tabulate(content, headers=column_names, tablefmt="rst")

    generated_dir = Path("generated")
    generated_dir.mkdir(exist_ok=True)
    with open(generated_dir / f"{table_name}_table.rst", "w+") as table_file:
        table_file.write(".. rst-class:: table-weights\n")  # Custom CSS class, see custom_torchvision.css
        table_file.write(".. table:: #{table_name} \n")
        table_file.write(f"    :widths: 100 {'20 ' * len(metrics_names)} 20 10\n\n")
        table_file.write(f"{textwrap.indent(table, ' ' * 4)}\n\n")


generate_weights_table(module=M, table_name="classification", metrics=[("acc@1", "Acc@1"), ("acc@5", "Acc@5")])
generate_weights_table(
    module=M.quantization, table_name="classification_quant", metrics=[("acc@1", "Acc@1"), ("acc@5", "Acc@5")]
)
generate_weights_table(
    module=M.detection, table_name="detection", metrics=[("box_map", "Box MAP")], exclude_patterns=["Mask", "Keypoint"]
)
generate_weights_table(
    module=M.detection,
    table_name="instance_segmentation",
    metrics=[("box_map", "Box MAP"), ("mask_map", "Mask MAP")],
    include_patterns=["Mask"],
)
generate_weights_table(
    module=M.detection,
    table_name="detection_keypoint",
    metrics=[("box_map", "Box MAP"), ("kp_map", "Keypoint MAP")],
    include_patterns=["Keypoint"],
)
generate_weights_table(
    module=M.segmentation, table_name="segmentation", metrics=[("miou", "Mean IoU"), ("pixel_acc", "pixelwise Acc")]
)
generate_weights_table(module=M.video, table_name="video", metrics=[("acc@1", "Acc@1"), ("acc@5", "Acc@5")])


def setup(app):

    app.connect("autodoc-process-docstring", inject_minigalleries)
    app.connect("autodoc-process-docstring", inject_weight_metadata)
