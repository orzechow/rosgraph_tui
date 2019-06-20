import sys
import urwid

import widgets


class Model:
    def __init__(self):
        self.choices = u'Chapman Cleese Gilliam Idle Jones Palin'.split()

    def handle_choice(self, choice):
        idx = self.choices.index(choice)
        idx = min(idx, len(self.choices) - 1)
        self.choices.remove(self.choices[idx])


class View:
    def __init__(self, choices):
        self.palette = [
            ('banner', 'black', 'light gray'),
            ('streak', 'black', 'dark red'),
            ('bg', 'black', 'dark blue'),
            ('reversed', 'standout', ''), ]

        self.main_widget = widgets.PaddedListFrame(u"your choice:", choices)

    def reset_list(self, choices):
        self.main_widget.reset_list(choices)


class Controller:
    def __init__(self):
        self.model = Model()
        self.view = View(self.model.choices)

        urwid.connect_signal(self.view.main_widget.list, 'choice', self.handle_choice)

        self.loop = urwid.MainLoop(self.view.main_widget, self.view.palette, unhandled_input=self.handle_input)

    def run(self):
        self.loop.run()

    def exit_on_q(self, key):
        if key in ('q', 'Q'):
            raise urwid.ExitMainLoop()

    def handle_input(self, key):
        self.exit_on_q(key)

    def handle_choice(self, list, button, choice):
        # workaround for urwid bug
        button.set_text("")
        self.model.handle_choice(choice)
        self.view.reset_list(self.model.choices)


def main(args=None):
    """The main routine."""
    c = Controller()
    c.run()

    # if args is None:
    #     args = sys.argv[1:]


if __name__ == "__main__":
    main()
