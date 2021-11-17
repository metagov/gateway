from setuptools import setup, find_packages

META_DATA = dict(
    name="metagov",
    version="1.0",
    author="metagovernance project",
    url="https://github.com/metagov-prototype/metagov",
    packages=find_packages(),
    scripts=["manage.py"],
)

if __name__ == "__main__":
    setup(**META_DATA)