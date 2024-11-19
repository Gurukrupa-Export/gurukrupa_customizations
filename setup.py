from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in gurukrupa_customizations/__init__.py
from gurukrupa_customizations import __version__ as version

setup(
	name="gurukrupa_customizations",
	version=version,
	description="Gurukrupa Customizations",
	author="8848 Digital LLP",
	author_email="deepak@8848digital.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
