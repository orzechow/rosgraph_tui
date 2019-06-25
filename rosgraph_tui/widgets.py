import urwid


class ListEntry(urwid.Text):
    _selectable = True

    signals = ["click"]

    def keypress(self, size, key):
        """
        Send 'click' signal on 'activate' command.
        """
        if self._command_map[key] != urwid.ACTIVATE:
            return key

        self._emit('click')

    def mouse_event(self, size, event, button, x, y, focus):
        """
        Send 'click' signal on button 1 press.
        """
        if button != 1 or not urwid.util.is_mouse_press(event):
            return False

        self._emit('click')
        return True


class List(urwid.ListBox):
    signals = ["choice"]

    def sizing(self):
        return frozenset([urwid.FIXED])

    def __init__(self, choices):
        self.choices_list = []
        self.set_choices(choices)

    def reset_widget(self):
        super(List, self).__init__(urwid.SimpleFocusListWalker(self.choices_list))

    def set_choices(self, choices):
        self.choices_list = []
        for c in choices:
            button = ListEntry(c)
            urwid.connect_signal(button, 'click', self.item_chosen, c)
            self.choices_list.append(urwid.AttrMap(button, None, focus_map='reversed'))
        self.reset_widget()

    def reset_list(self, choices):
        focus = self.focus
        if focus:
            if focus.original_widget.get_text() in choices:
                focus_position = choices.index(focus.original_widget.get_text())
            else:
                focus_position = self.focus_position
                focus_position = max(0, min(focus_position, len(choices) - 1))
        else:
            focus_position = 0

        self.set_choices(choices)
        if len(choices) > 0:
            self.focus_position = focus_position

    def item_chosen(self, button, choice):
        self._emit('choice', button, choice)


class PaddedListFrame(urwid.Padding):
    def sizing(self):
        return frozenset([urwid.FIXED])

    def __init__(self, title, choices):
        self.title = title

        self.header = urwid.Pile([('pack', urwid.Text(self.title)), ('pack', urwid.Divider())])
        self.list = List(choices)
        self.footer = urwid.Pile([('pack', urwid.Divider()), ('pack', urwid.Text("FOOOTER"))])

        body = urwid.Frame(self.list, self.header, self.footer)
        super(PaddedListFrame, self).__init__(body, left=2, right=2)

    def reset_list(self, choices):
        self.list.reset_list(choices)


class ListColumn(urwid.Columns):
    def __init__(self, choices_left, choices_middle, choices_right):
        self.column_left = PaddedListFrame(u"Input:", choices_left)
        self.column_middle = PaddedListFrame(u"middle choice:", choices_middle)
        self.column_right = PaddedListFrame(u"Output:", choices_right)

        body = [self.column_left] + [self.column_middle] + [self.column_right]
        super(ListColumn, self).__init__(body)

    def reset_list(self, choices, column):
        if column == 'left':
            self.column_left.reset_list(choices)
        elif column == 'middle':
            self.column_middle.reset_list(choices)
        elif column == 'right':
            self.column_right.reset_list(choices)
