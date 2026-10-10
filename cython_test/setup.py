from setuptools import Extension, setup
from Cython.Build import cythonize

extensions = [
    Extension(
        name="hello",
        sources=["hello.pyx"],
    )
]

setup(
    name="cython-smoke-test",
    ext_modules=cythonize(
        extensions,
        compiler_directives={"language_level": "3"},
    ),
)