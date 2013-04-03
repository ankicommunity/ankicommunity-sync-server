
from setuptools import setup, find_packages

setup(
    name="AnkiServer",
    version="0.0.1",
    description="Provides the a RESTful API to manipulating Anki decks",
    author="David Snopek",
    author_email="dsnopek@gmail.com",
    install_requires=["PasteDeploy>=1.3.2"],
    # TODO: should these really be in install_requires?
    requires=["webob(>=0.9.7)"],
    test_suite='nose.collector',
    entry_points="""
    [paste.app_factory]
    deckapp = AnkiServer.deck:make_app
    syncapp = AnkiServer.sync:make_app

    [paste.server_runner]
    server = AnkiServer:server_runner
    """,
)

