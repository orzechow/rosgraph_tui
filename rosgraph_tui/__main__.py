from enum import Enum
import sys
import urwid

import model
import widgets


class View:
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
            ('reversed', 'bold', '')]

        self.main_widget = widgets.ListColumn(choices_left, choices_middle, choices_right)
        self.main_widget_with_attr = urwid.AttrMap(self.main_widget, 'bg')

    def get_selection(self):
        return self.main_widget.get_selection()

    def set_title(self, title):
        self.main_widget.set_title(title)

    def set_focus(self, column):
        self.main_widget.set_focus(column.index)

    def reset_list(self, choices, column):
        self.main_widget.reset_list(choices, column)


class Controller:
    Modes = Enum('NODES_AND_TOPICS', 'NODES', 'TOPICS')
    ListEntryTypes = Enum('NODE', 'TOPIC')

    def __init__(self):
        self.main_mode = self.Modes.NODES_AND_TOPICS
        self.choice = ''
        self.choice_type = self.ListEntryTypes.NODE

        self.model = model.Model()

        self.view = View([], [], [])
        self.view.set_focus(self.view.Columns.MIDDLE)

        self.update_view()

        urwid.connect_signal(self.view.main_widget.column_left.list, 'choice', self.handle_choice,
                             self.view.Columns.LEFT)
        urwid.connect_signal(self.view.main_widget.column_middle.list, 'choice', self.handle_choice,
                             self.view.Columns.MIDDLE)
        urwid.connect_signal(self.view.main_widget.column_right.list, 'choice', self.handle_choice,
                             self.view.Columns.RIGHT)

        self.loop = urwid.MainLoop(self.view.main_widget_with_attr, self.view.palette, unhandled_input=self.handle_input)

    def run(self):
        self.loop.run()

    def exit_on_q(self, key):
        if key in ('q', 'Q'):
            raise urwid.ExitMainLoop()

    def show_all_on_esc(self, key):
        if key == 'esc':
            if self.main_mode == self.Modes.NODES and len(self.model.main_node_list) == 1:
                self.model.main_node_list = self.model.graph.get_nodes()
            elif self.main_mode == self.Modes.TOPICS and len(self.model.main_topic_list) == 1:
                self.model.main_topic_list = self.model.graph.get_topics()
            else:
                self.main_mode = self.Modes.NODES_AND_TOPICS
                self.model.main_node_list = self.model.graph.get_nodes()
                self.model.main_topic_list = self.model.graph.get_topics()
                self.model.input_list = []
                self.model.output_list = []

            self.update_view()
            self.view.set_focus(self.view.Columns.MIDDLE)

    def choose_on_arrow_out_of_view(self, key):
        if key == 'left':
            selection = self.view.get_selection()
            if selection:
                self.handle_choice(None, None, selection, self.view.Columns.LEFT)
        elif key == 'right':
            selection = self.view.get_selection()
            if selection:
                self.handle_choice(None, None, selection, self.view.Columns.RIGHT)

    def handle_input(self, key):
        self.exit_on_q(key)
        self.show_all_on_esc(key)
        self.choose_on_arrow_out_of_view(key)

    def handle_node_choice(self, node):
        self.model.main_topic_list = []
        self.model.main_node_list = [node]
        self.model.input_list = self.model.graph.get_subscriptions(node)
        self.model.output_list = self.model.graph.get_publications(node)

    def handle_topic_choice(self, topic):
        self.model.main_topic_list = [topic]
        self.model.main_node_list = []
        self.model.input_list = self.model.graph.get_publishers(topic)
        self.model.output_list = self.model.graph.get_subscribers(topic)

    def handle_input_output_choice(self, choice):
        if self.main_mode == self.Modes.NODES:
            self.handle_topic_choice(choice)
        elif self.main_mode == self.Modes.TOPICS:
            self.handle_node_choice(choice)
        else:
            raise RuntimeError("choice from left or right list should not be possible in NODES_AND_TOPICS mode!")

    def handle_main_choice(self, choice):
        if self.main_mode == self.Modes.NODES:
            self.handle_node_choice(choice)
        elif self.main_mode == self.Modes.TOPICS:
            self.handle_topic_choice(choice)
        else:
            choice_name, choice_type = self.get_list_entry(choice)
            self.choice = choice_name
            if choice_type == self.ListEntryTypes.NODE:
                self.main_mode = self.Modes.NODES
                self.handle_node_choice(choice_name)
            elif choice_type == self.ListEntryTypes.TOPIC:
                self.main_mode = self.Modes.TOPICS
                self.handle_topic_choice(choice_name)
            else:
                raise TypeError("choice is neither node nor topic: " + choice)

    def handle_choice(self, list, button, choice, column):
        self.choice = choice
        if column == self.view.Columns.LEFT or column == self.view.Columns.RIGHT:
            self.handle_input_output_choice(choice)
            self.switch_mode()
        elif column == self.view.Columns.MIDDLE:
            self.handle_main_choice(choice)
        else:
            raise TypeError("column is neither left, right nor middle!")

        self.update_view()
        self.view.set_focus(self.view.Columns.MIDDLE)

    def switch_mode(self):
        if self.main_mode == self.Modes.NODES:
            self.main_mode = self.Modes.TOPICS
        elif self.main_mode == self.Modes.TOPICS:
            self.main_mode = self.Modes.NODES
        else:
            raise RuntimeError("switch_mode() should not be called in NODES_AND_TOPICS mode!")

    def get_list_entry(self, list_entry):
        if self.main_mode == self.Modes.NODES_AND_TOPICS:
            if "N " in list_entry:
                return list_entry[2:], self.ListEntryTypes.NODE
            elif "T " in list_entry:
                return list_entry[2:], self.ListEntryTypes.TOPIC
            else:
                raise TypeError("list entry is neither node nor topic: " + list_entry)
        else:
            raise RuntimeError("get_list_entry() should only be called in NODES_AND_TOPICS mode, but mode is: " + self.main_mode)

    def generate_node_style(self, name):
        if name == self.choice:
            return 'chosen_node', name
        else:
            return 'node', name

    def generate_topic_style(self, name):
        if name == self.choice:
            return 'chosen_topic', name
        else:
            return 'topic', name

    def update_view(self):
        if self.main_mode == self.Modes.NODES_AND_TOPICS:
            nodes = ["N " + name for name in self.model.main_node_list]
            topics = ["T " + name for name in self.model.main_topic_list]
        else:
            nodes = self.model.main_node_list
            topics = self.model.main_topic_list

        nodes = [self.generate_node_style(name) for name in nodes]
        topics = [self.generate_topic_style(name) for name in topics]

        if self.main_mode == self.Modes.NODES:
            input = [self.generate_topic_style(name) for name in self.model.input_list]
            output = [self.generate_topic_style(name) for name in self.model.output_list]
        else:
            input = [self.generate_node_style(name) for name in self.model.input_list]
            output = [self.generate_node_style(name) for name in self.model.output_list]

        self.view.reset_list(input, self.view.Columns.LEFT)
        self.view.reset_list(nodes + topics, self.view.Columns.MIDDLE)
        self.view.reset_list(output, self.view.Columns.RIGHT)
        self.view.set_title(str(self.main_mode).replace('_', ' ').title() + ':')


def main(args=None):
    """The main routine."""
    c = Controller()
    c.run()

    # if args is None:
    #     args = sys.argv[1:]


if __name__ == "__main__":
    main()
