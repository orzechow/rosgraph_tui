"""Kept for colcon / ament_python.  All metadata lives in pyproject.toml.

Two things PEP 621 cannot express are done here:

* the ament index resource marker and package.xml are installed as
  ``data_files``;
* colcon-python-setup-py introspects ``setup.py`` by ``repr()``-ing the
  Distribution and ``ast.literal_eval``-ing the result, which breaks on the
  ``SpecifierSet`` that setuptools stores for ``requires-python`` when it
  comes from pyproject.toml.  ``_Distribution`` turns it back into the plain
  string that a ``python_requires=`` keyword would have produced.
"""

from setuptools import Distribution, setup

package_name = "rosgraph_tui"


class _Distribution(Distribution):
    def parse_config_files(self, filenames=None, ignore_option_errors=False):
        super().parse_config_files(filenames=filenames, ignore_option_errors=ignore_option_errors)
        for obj in (self, self.metadata):
            value = getattr(obj, "python_requires", None)
            if value is not None and not isinstance(value, str):
                obj.python_requires = str(value)


setup(
    distclass=_Distribution,
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
)
