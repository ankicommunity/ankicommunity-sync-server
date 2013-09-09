
from setuptools import setup, find_packages

setup(
    name="AnkiServer",
    version="2.0.0dev",
    description="A personal Anki sync server (so you can sync against your own server rather than AnkiWeb)",
    author="David Snopek",
    author_email="dsnopek@gmail.com",
    url="https://github.com/dsnopek/anki-sync-server",
    install_requires=["PasteDeploy>=1.3.2"],
    # TODO: should these really be in install_requires?
    requires=["webob(>=0.9.7)"],
    test_suite='nose.collector',
    entry_points="""
    [paste.app_factory]
    sync_app = AnkiServer.apps.sync_app:make_app
    rest_app = AnkiServer.apps.rest_app:make_app

    [paste.server_runner]
    server = AnkiServer:server_runner
    """,
)

