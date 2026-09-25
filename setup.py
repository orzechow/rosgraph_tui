import re
from pathlib import Path

from setuptools import find_packages, setup

package_name = "rosgraph_tui"
here = Path(__file__).parent
long_description = (here / "README.md").read_text()
version = re.search(r'__version__ = "([^"]+)"', (here / package_name / "__init__.py").read_text()).group(1)

setup(
    name=package_name,
    version=version,
    author="Piotr Orzechowski",
    author_email="orzechow@posteo.de",
    maintainer="Piotr Orzechowski",
    maintainer_email="orzechow@posteo.de",
    description="An interactive terminal user interface (TUI) to explore and debug your ROS 2 graph.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/orzechow/rosgraph_tui",
    packages=find_packages(exclude=["test", "test.*"]),
    package_data={package_name: ["*.tcss", "fixtures/*.json"]},
    include_package_data=True,
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    license="MIT",
    python_requires=">=3.10",
    # rclpy is deliberately absent: it comes from the sourced ROS 2 installation.
    install_requires=[
        "textual>=8,<9",
        "rapidfuzz>=3",
    ],
    extras_require={
        "dev": ["pytest>=7", "pytest-asyncio>=0.23", "ruff"],
    },
    classifiers=[
        "Environment :: Console",
        "Framework :: Robot Framework :: Tool",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Operating System :: Unix",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Debuggers",
    ],
    entry_points={
        "console_scripts": [
            "rosgraph_tui = rosgraph_tui.cli:main",
        ]
    },
    zip_safe=False,
)
