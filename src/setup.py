from setuptools import setup, find_packages

# TODO: Generate from or parse values from pyproject.toml.
setup(
    name="anki-sync-server",
    version="2.4.0",
    description="Self-hosted Anki Sync Server.",
    author="Anki Community",
    author_email="kothary.vikash+ankicommunity@gmail.com",
    packages=find_packages(),
    url='https://ankicommunity.github.io/'
)
