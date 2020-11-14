"""deathbeds generalized automation framework."""
__version__ = __import__("datetime").date.today().strftime("%Y.%m.%d")
from . import util
from .util import File, merge, Module


def main():
    from . import __main__
    __main__.app()
