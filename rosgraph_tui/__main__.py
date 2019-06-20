import sys
import urwid


class Model:
    def __init__(self):
        self.text = u" Hello World "


class TextView(urwid.AttrMap):
    def __init__(self):
        self.txt = urwid.Text(('banner', u" init "), align='center')
        self.map1 = urwid.AttrMap(self.txt, 'streak')
        self.fill = urwid.Filler(self.map1)
        super(TextView, self).__init__(self.fill, 'bg')


class View:
    def __init__(self):
        self.palette = [
            ('banner', 'black', 'light gray'),
            ('streak', 'black', 'dark red'),
            ('bg', 'black', 'dark blue'), ]

        self.main_view = TextView()

    def set_text(self, txt):
        self.main_view.txt.set_text(('banner', txt))


class Controller:
    def __init__(self):
        self.model = Model()
        self.banner = View()
        self.loop = urwid.MainLoop(self.banner.main_view, self.banner.palette, unhandled_input=self.handle_input)

    def run(self):
        self.loop.run()

    def exit_on_q(self, key):
        if key in ('q', 'Q'):
            raise urwid.ExitMainLoop()
        self.banner.set_text(self.model.text)

    def handle_input(self, key):
        self.exit_on_q(key)



def main(args=None):
    """The main routine."""
    c = Controller()
    c.run()

    # if args is None:
    #     args = sys.argv[1:]


if __name__ == "__main__":
    main()
