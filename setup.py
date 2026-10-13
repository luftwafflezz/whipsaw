from setuptools import Extension, setup

setup(
    ext_modules=[
        Extension(
            name="whipsaw.accuraterip",
            libraries=['sndfile'],
            sources=["src/accuraterip-checksum.c"],
        ),
    ]
)
