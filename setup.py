import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name='rosgraph_tui',
    version='0.0.1',
    author='Piotr Orzechowski',
    author_email='orzechow@posteo.de',
    description='An interactive terminal user interface (TUI) to explore and debug your ROS graph.',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/orzechow/rosgraph_tui',
    packages=setuptools.find_packages(),
    license='MIT',
    classifiers=[
        "Environment :: Console",
        "Framework :: Robot Framework :: Tool",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Operating System :: Unix",
        "Programming Language :: Python :: 2",
        "Topic :: Software Development"
    ]
)
