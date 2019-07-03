import sys
import urwid

import widgets


class Model:
    def __init__(self):
        self.choices_left = u'Chapman Cleese Gilliam Idle Jones Palin'.split()
        self.choices_middle = u'Chapman Cleese Gilliam Idle Jones Palin'.split()
        self.choices_right = u'Chapman Cleese Gilliam Idle Jones Palin'.split()

    def handle_choice(self, list, choice):
        idx = list.index(choice)
        idx = min(idx, len(list) - 1)
        list.remove(list[idx])


class View:
    def __init__(self, choices_left, choices_middle, choices_right):
        self.Columns = widgets.ListColumn.Columns

        self.palette = [
            ('banner', 'black', 'light gray'),
            ('streak', 'black', 'dark red'),
            ('bg', 'black', 'dark blue'),
            ('reversed', 'standout', ''), ]

        self.main_widget = widgets.ListColumn(choices_left, choices_middle, choices_right)

    def reset_list(self, choices, column):
        self.main_widget.reset_list(choices, column)


class Controller:
    def __init__(self):
        self.model = Model()
        self.view = View(self.model.choices_left, self.model.choices_middle, self.model.choices_right)

        urwid.connect_signal(self.view.main_widget.column_left.list, 'choice', self.handle_choice, self.view.Columns.LEFT)
        urwid.connect_signal(self.view.main_widget.column_middle.list, 'choice', self.handle_choice, self.view.Columns.MIDDLE)
        urwid.connect_signal(self.view.main_widget.column_right.list, 'choice', self.handle_choice, self.view.Columns.RIGHT)

        self.loop = urwid.MainLoop(self.view.main_widget, self.view.palette, unhandled_input=self.handle_input)

    def run(self):
        self.loop.run()

    def exit_on_q(self, key):
        if key in ('q', 'Q'):
            raise urwid.ExitMainLoop()

    def handle_input(self, key):
        self.exit_on_q(key)

    def handle_choice(self, list, button, choice, column):
        if column == self.view.Columns.LEFT:
            self.model.handle_choice(self.model.choices_left, choice)
            self.view.reset_list(self.model.choices_left, column)
        elif column == self.view.Columns.MIDDLE:
            self.model.handle_choice(self.model.choices_middle, choice)
            self.view.reset_list(self.model.choices_middle, column)
        elif column == self.view.Columns.RIGHT:
            self.model.handle_choice(self.model.choices_right, choice)
            self.view.reset_list(self.model.choices_right, column)


def main(args=None):
    """The main routine."""
    c = Controller()
    c.run()

    # if args is None:
    #     args = sys.argv[1:]


if __name__ == "__main__":
    main()
