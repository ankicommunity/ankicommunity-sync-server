
def setup_logging(config_file=None):
    """Setup logging based on a config_file."""

    import logging

    if config_file is not None:
        # monkey patch the logging.config.SMTPHandler if necessary
        import sys
        if sys.version_info[0] == 2 and sys.version_info[1] == 5:
            import AnkiServer.logpatch

        # load the config file
        import logging.config
        logging.config.fileConfig(config_file)
    else:
        logging.getLogger().setLevel(logging.INFO)

