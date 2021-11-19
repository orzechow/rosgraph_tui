import signal

import urwid

from rosgraph_tui.controller import Controller


def sigint_handler(sig, frame):
    raise urwid.ExitMainLoop()


def main(args=None):
    """The main routine."""
    signal.signal(signal.SIGINT, sigint_handler)
    c = Controller()
    c.run()

    # if args is None:
    #     args = sys.argv[1:]


if __name__ == "__main__":
    main()
