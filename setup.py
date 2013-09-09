
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(
    name="AnkiServer",
    version="2.0.0a3",
    description="A personal Anki sync server (so you can sync against your own server rather than AnkiWeb)",
    long_description=open('README.rst').read(),
    license='LICENSE.txt',
    author="David Snopek",
    author_email="dsnopek@gmail.com",
    url="https://github.com/dsnopek/anki-sync-server",
    install_requires=["PasteDeploy>=1.3.2"],
    # TODO: should these really be in install_requires?
    requires=["webob(>=0.9.7)"],
    test_suite='nose.collector',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Environment :: Web Environment',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Topic :: Education',
        'Topic :: Education :: Computer Aided Instruction (CAI)',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Application',
        'Topic :: Utilities',
    ],
    entry_points="""
    [paste.app_factory]
    sync_app = AnkiServer.apps.sync_app:make_app
    rest_app = AnkiServer.apps.rest_app:make_app

    [paste.server_runner]
    server = AnkiServer:server_runner
    """,
)

