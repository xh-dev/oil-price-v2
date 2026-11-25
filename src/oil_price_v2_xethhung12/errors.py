class OilPriceError(Exception):
    """Expected failure (network, bad input, bad decode result).

    The command line prints the message and exits with code 1 instead of
    showing a traceback.
    """

