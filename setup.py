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
    install_requires=[
        "PyQt5",
        "motmot",
        "tomial_odometry @ git+ssh://git@github.com/bwoodsend/tomial_odometry.git@982d1d758c24328ed25e180ef046859d6bc52478",
        "pangolin @ git+ssh://git@github.com/bwoodsend/pangolin.git@5ac604917ef59db3ef020894835249658fea2510",
        "vtkplotlib >= 1.5.0",
    ],
    extras_require={
        "test": [
            "pytest>=3",
            "pytest-order",
            "coverage",
            "pytest-cov",
            "tomial_tooth_collection_api @ git+ssh://git@github.com/bwoodsend/tomial_tooth_collection_api.git@0bd1fe8b9b82558712b38ce276a3633c7600bad5",
        ]
    },
    license="BSD license",
    long_description=readme,
    name='tomial-clicky-tooth',
    packages=find_packages(include=['tomial_clicky_tooth']),
    url='https://github.com/bwoodsend/tomial-clicky-tooth',
    version="0.1.0",
    zip_safe=False,
)
