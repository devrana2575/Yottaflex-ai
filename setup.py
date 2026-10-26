from setuptools import setup, find_packages

setup(
    name="yottaflex",
    version="1.0.0",
    description="Industrial Pump, Tank, Valve and Flow Anomaly Detection Simulator",
    author="YottaFlex Candidate",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "numpy>=1.26.0",
        "pandas>=2.2.0",
        "networkx>=3.3",
        "pydantic>=2.7.0",
        "click>=8.1.0",
        "rich>=13.7.0",
    ],
    entry_points={
        "console_scripts": [
            "yottaflex=yottaflex.cli:cli",
        ],
    },
    python_requires=">=3.11",
)
