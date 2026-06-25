from setuptools import setup, find_packages

setup(
    name="kvault",
    version="1.0.0",
    description="Redis-compatible in-memory key-value store with RESP protocol",
    author="Ushasri Dasari",
    author_email="ushasri.dasari92@gmail.com",
    python_requires=">=3.10",
    packages=find_packages(exclude=["tests*"]),
    entry_points={
        "console_scripts": [
            "kvault-server=main:main",
            "kvault-client=client:main",
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
)
