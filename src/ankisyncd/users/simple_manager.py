import os
from ankisyncd import logging

logger = logging.get_logger(__name__)


class SimpleUserManager:
    """A simple user manager that always allows any user."""

    def __init__(self, collection_path=""):
        self.collection_path = collection_path

    def authenticate(self, username, password):
        """
        Returns True if this username is allowed to connect with this password.
        False otherwise. Override this to change how users are authenticated.
        """

        return True

    def userdir(self, username):
        """
        Returns the directory name for the given user. By default, this is just
        the username. Override this to adjust the mapping between users and
        their directory.
        """

        return username

    def _create_user_dir(self, username):
        user_dir_path = os.path.join(self.collection_path, username)
        if not os.path.isdir(user_dir_path):
            logger.info(
                "Creating collection directory for user '{}' at {}".format(
                    username, user_dir_path
                )
            )
            os.makedirs(user_dir_path)
