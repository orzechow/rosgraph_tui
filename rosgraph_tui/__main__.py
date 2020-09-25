from enum import Enum
import sys
import signal

import urwid

import model
import view


class Controller:
    Modes = Enum('NODES_AND_TOPICS', 'NODES', 'TOPICS')
    InputLabels = {'NODES_AND_TOPICS': 'Input', 'NODES': 'Subscriptions', 'TOPICS': 'Publishers'}
    OutputLabels = {'NODES_AND_TOPICS': 'Output', 'NODES': 'Publications', 'TOPICS': 'Subscribers'}

    def __init__(self):
        self.main_mode = self.Modes.NODES_AND_TOPICS

        self.model = model.Model()

        self.view = view.MainView([], [], [])
        self.view.set_focus(self.view.Columns.MIDDLE)

        self.filter_string = ''
        self.choice = ''
        self.choice_type = self.model.ListEntryTypes.NODE

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

    def show_all_or_exit_on_esc(self, key):
        if key == 'esc':
            is_node_selected = len(self.model.main_node_list) == 1
            is_topic_selected = len(self.model.main_topic_list) == 1
            is_node_filter_active = len(self.model.main_node_list) != len(self.model.graph.get_nodes())
            is_topic_filter_active = len(self.model.main_topic_list) != len(self.model.graph.get_topics())

            if self.filter_string != '':
                self.filter_string = ''

            if self.main_mode == self.Modes.NODES and (is_node_selected or is_node_filter_active):
                self.model.set_main_node_list(self.model.graph.get_nodes(self.filter_string))
            elif self.main_mode == self.Modes.TOPICS and (is_topic_selected or is_topic_filter_active):
                self.model.set_main_topic_list(self.model.graph.get_topics(self.filter_string))
            elif is_node_filter_active or is_topic_filter_active:
                self.main_mode = self.Modes.NODES_AND_TOPICS
                self.model.set_main_node_list(self.model.graph.get_nodes(self.filter_string))
                self.model.set_main_topic_list(self.model.graph.get_topics(self.filter_string))
                self.model.set_input_list([])
                self.model.set_output_list([])
            else:
                raise urwid.ExitMainLoop()

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

    def update_filter(self, key):
        if key in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_/':
            self.filter_string = self.filter_string + key
            return True
        elif key == 'backspace':
            self.filter_string = self.filter_string[:-1]
            return True
        return False

    def handle_input(self, key):
        self.show_all_or_exit_on_esc(key)
        self.choose_on_arrow_out_of_view(key)
        if self.update_filter(key):
            if self.main_mode == self.Modes.NODES or self.main_mode == self.Modes.NODES_AND_TOPICS:
                self.model.set_main_node_list(self.model.graph.get_nodes(self.filter_string))
            if self.main_mode == self.Modes.TOPICS or self.main_mode == self.Modes.NODES_AND_TOPICS:
                self.model.set_main_topic_list(self.model.graph.get_topics(self.filter_string))
            self.view.main_widget.set_focus_column(self.view.Columns.MIDDLE.index)
            self.update_view()

    def handle_node_choice(self, node):
        self.model.set_main_node_list([node])
        self.model.set_main_topic_list([])
        self.model.set_input_list(self.model.graph.get_subscriptions(node), self.model.ListEntryTypes.TOPIC)
        self.model.set_output_list(self.model.graph.get_publications(node), self.model.ListEntryTypes.TOPIC)

    def handle_topic_choice(self, topic):
        self.model.set_main_node_list([topic])
        self.model.set_main_topic_list([])
        self.model.set_input_list(self.model.graph.get_publishers(topic), self.model.ListEntryTypes.NODE)
        self.model.set_output_list(self.model.graph.get_subscribers(topic), self.model.ListEntryTypes.NODE)

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
            if choice_type == self.model.ListEntryTypes.NODE:
                self.main_mode = self.Modes.NODES
                self.handle_node_choice(choice_name)
            elif choice_type == self.model.ListEntryTypes.TOPIC:
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

        self.filter_string = ''
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
                return list_entry[2:], self.model.ListEntryTypes.NODE
            elif "T " in list_entry:
                return list_entry[2:], self.model.ListEntryTypes.TOPIC
            else:
                raise TypeError("list entry is neither node nor topic: " + list_entry)
        else:
            raise RuntimeError("get_list_entry() should only be called in NODES_AND_TOPICS mode, but mode is: " + str(self.main_mode))

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
            nodes = ["N " + node.name for node in self.model.main_node_list]
            topics = ["T " + node.name for node in self.model.main_topic_list]
        else:
            nodes = [node.name for node in self.model.main_node_list]
            topics = [node.name for node in self.model.main_topic_list]

        nodes = [self.generate_node_style(name) for name in nodes]
        topics = [self.generate_topic_style(name) for name in topics]

        if self.main_mode == self.Modes.NODES:
            input = [self.generate_topic_style(item.name) for item in self.model.input_list]
            output = [self.generate_topic_style(item.name) for item in self.model.output_list]
        else:
            input = [self.generate_node_style(item.name) for item in self.model.input_list]
            output = [self.generate_node_style(item.name) for item in self.model.output_list]

        self.view.reset_list(input, self.view.Columns.LEFT)
        self.view.reset_list(nodes + topics, self.view.Columns.MIDDLE)
        self.view.reset_list(output, self.view.Columns.RIGHT)
        self.view.set_title(self.InputLabels[str(self.main_mode)] + ':', self.view.Columns.LEFT)
        self.view.set_title(str(self.main_mode).replace('_', ' ').title() + ':', self.view.Columns.MIDDLE)
        self.view.set_title(self.OutputLabels[str(self.main_mode)] + ':', self.view.Columns.RIGHT)
        self.view.set_footer(self.filter_string, self.view.Columns.MIDDLE)


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
