from enum import Enum

import urwid


class ListEntry(urwid.Text):
    _selectable = True

    signals = ["click"]

    def __init__(self, item):
        self.original_item = item
        super(ListEntry, self).__init__(item.name_string())

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
        self.choices_widgets = []
        self.set_choices(choices)

    def reset_widget(self):
        super(List, self).__init__(
            urwid.SimpleFocusListWalker(self.choices_widgets))

    def set_choices(self, choices):
        self.choices_widgets = []
        for style, item in choices:
            button = ListEntry(item)
            urwid.connect_signal(button, 'click', self.item_chosen, item)
            self.choices_widgets.append(urwid.AttrMap(
                button, style, focus_map='reversed'))
        self.reset_widget()

    def reset_list(self, choices):
        choices_names = [item[1].name_string() for item in choices]
        focus = self.focus
        if focus:
            if focus.original_widget.get_text() in choices_names:
                focus_position = choices_names.index(
                    focus.original_widget.get_text())
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
        self.header = urwid.Pile(
            [('pack', urwid.Text(('header', title))), ('pack', urwid.Divider())])
        self.list = List(choices)
        self.footer = urwid.Pile(
            [('pack', urwid.Divider()), ('pack', urwid.Text(('footer', '')))])

        body = urwid.Frame(self.list, self.header, self.footer)
        super(PaddedListFrame, self).__init__(body, left=2, right=2)

    def get_selection(self):
        if self.original_widget.body.focus:
            return self.original_widget.body.focus.base_widget.original_item
        else:
            return None

    def set_title(self, title):
        self.header[0].set_text(('header', title))

    def set_footer(self, footer):
        self.footer[1].set_text(('footer', footer))

    def reset_list(self, choices):
        self.list.reset_list(choices)


class ListColumn(urwid.Columns):

    class Columns(Enum):
        LEFT = 0
        MIDDLE = 1
        RIGHT = 2

    def __init__(self, choices_left, choices_middle, choices_right):
        self.column_left = PaddedListFrame(u"Input:", choices_left)
        self.column_middle = PaddedListFrame(u"middle choice:", choices_middle)
        self.column_right = PaddedListFrame(u"Output:", choices_right)

        body = [self.column_left] + [self.column_middle] + [self.column_right]
        super(ListColumn, self).__init__(body)

    def get_selection(self):
        if self.focus:
            return self.focus.get_selection()
        else:
            None

    def get_selection_index(self):
        if self.focus and self.focus.base_widget.body.focus:
            return self.focus.base_widget.body.focus_position
        else:
            None

    def get_selected_column(self):
        if self.focus:
            return self.focus_col
        else:
            None

    def set_title(self, title, column):
        if column == self.Columns.LEFT or column == self.Columns.LEFT.value:
            self.column_left.set_title(title)
        elif column == self.Columns.MIDDLE or column == self.Columns.MIDDLE.value:
            self.column_middle.set_title(title)
        elif column == self.Columns.RIGHT or column == self.Columns.RIGHT.value:
            self.column_right.set_title(title)

    def set_footer(self, footer, column):
        if column == self.Columns.LEFT or column == self.Columns.LEFT.value:
            self.column_left.set_footer(footer)
        elif column == self.Columns.MIDDLE or column == self.Columns.MIDDLE.value:
            self.column_middle.set_footer(footer)
        elif column == self.Columns.RIGHT or column == self.Columns.RIGHT.value:
            self.column_right.set_footer(footer)

    def reset_list(self, choices, column):
        if column == self.Columns.LEFT or column == self.Columns.LEFT.value:
            self.column_left.reset_list(choices)
        elif column == self.Columns.MIDDLE or column == self.Columns.MIDDLE.value:
            self.column_middle.reset_list(choices)
        elif column == self.Columns.RIGHT or column == self.Columns.RIGHT.value:
            self.column_right.reset_list(choices)
