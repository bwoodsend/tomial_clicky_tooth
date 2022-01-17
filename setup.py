from setuptools import setup, find_packages
import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent

readme = (HERE / 'README.rst').read_text("utf-8")

setup(
    author="Brénainn Woodsend",
    author_email='bwoodsend@gmail.com',
    python_requires='>=3.6',
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
    description="A PyQt5 based user interface for manually inspecting and "
    "placing landmarks on dental models.",
    install_requires=[],
    extras_require={
        "test": ['pytest>=3', 'pytest-order', 'coverage', 'pytest-cov']
    },
    license="BSD license",
    long_description=readme,
    name='tomial-clicky-tooth',
    packages=find_packages(include=['tomial_clicky_tooth']),
    url='https://github.com/bwoodsend/tomial-clicky-tooth',
    version="0.1.0",
    zip_safe=False,
)
