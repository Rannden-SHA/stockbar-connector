from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

from stockbar_connector import __version__ as version

setup(
    name="stockbar_connector",
    version=version,
    description="StockBar Cloud Connector for ERPNext - Syncs POS data with StockBar-WEB",
    author="Gisbert Distribuciones",
    author_email="info@stockbar.pro",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
