import urwid

from rosgraph_tui import widgets


class MainView:
    def __init__(self, choices_left, choices_middle, choices_right):
        self.Columns = widgets.ListColumn.Columns

        self.palette = [
            ('banner', 'black', 'light gray'),
            ('streak', 'black', 'dark red'),
            ('bg', 'black', 'black'),
            ('header', 'light gray,bold', 'black'),
            ('footer', 'light gray', 'black'),
            ('node', 'light gray', 'black'),
            ('topic', 'dark cyan', 'black'),
            ('chosen_node', 'light gray,bold', 'black'),
            ('chosen_topic', 'dark cyan,bold', 'black'),
            ('unconnected', 'dark red', 'black'),
            ('reversed', 'bold', '')]

        self.main_widget = widgets.ListColumn(choices_left, choices_middle, choices_right)
        self.main_widget_with_attr = urwid.AttrMap(self.main_widget, 'bg')

    def get_selection(self):
        return self.main_widget.get_selection()

    def get_selection_index(self):
        return self.main_widget.get_selection_index()

    def get_selected_column(self):
        return self.main_widget.get_selected_column()

    def set_title(self, title, column):
        self.main_widget.set_title(title, column)

    def set_footer(self, footer, column):
        self.main_widget.set_footer(footer, column)

    def set_focus(self, column):
        self.main_widget.set_focus(column.value)

    def reset_list(self, choices, column):
        self.main_widget.reset_list(choices, column)
