from setuptools import setup, find_packages
import os
import re


def get_version() -> str:
    cwd = os.path.dirname(__file__)
    with open(os.path.join(cwd, "oaaclient", "__init__.py")) as f:
        init_contents = f.read()

    version_match = re.search(r'''__version__ = ['"]([0-9.]+.*)['"]''', init_contents)
    if version_match:
        return version_match.group(1)
    else:
        raise RuntimeError("Unable to find version string.")


setup(
    name="oaaclient",
    version=get_version(),
    entry_points={
        'console_scripts': ['oaaclient=oaaclient.client:main'],
    }
)
