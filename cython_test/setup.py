from setuptools import Extension, setup
from Cython.Build import cythonize

extensions = [
    Extension(
        name="hello",
        sources=["hello.pyx"],
    ),
    Extension(
        name="cython_orderbook",
        sources=["cython_orderbook.pyx"],
    ),
]

setup(
    name="chronosmatch-cython-prototype",
    ext_modules=cythonize(
        extensions,
        compiler_directives={"language_level": "3"},
    ),
)