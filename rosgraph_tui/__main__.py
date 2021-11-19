from enum import Enum
import sys
import signal

import urwid
from click import secho

from rosnode import ROSNodeIOException

from rosgraph_tui import model
from rosgraph_tui.model import Modes
from rosgraph_tui import view


class Controller:

    InputLabels = {'Modes.NODES_AND_TOPICS': 'Input',
                   'Modes.NODES': 'Subscriptions', 'Modes.TOPICS': 'Publishers'}
    MiddleLabels = {'Modes.NODES_AND_TOPICS': 'Nodes and Topics',
                    'Modes.NODES': 'Nodes', 'Modes.TOPICS': 'Topics'}
    OutputLabels = {'Modes.NODES_AND_TOPICS': 'Output',
                    'Modes.NODES': 'Publications', 'Modes.TOPICS': 'Subscribers'}

    def __init__(self):
        try:
            self.model = model.Model()
        except ROSNodeIOException:
            secho("Failed to connect to ROS! "
                  "Please launch your stack before running rosgraph_tui", fg='red')
            exit()

        if self.model.main_list.count == 0:
            secho("No nodes and topics found! "
                  "Please launch your stack before running rosgraph_tui", fg='red')
            exit()

        self.view = view.MainView([], [], [])
        self.view.set_focus(self.view.Columns.MIDDLE)

        self.update_view()

        urwid.connect_signal(self.view.main_widget.column_left.list, 'choice', self.handle_choice,
                             self.view.Columns.LEFT)
        urwid.connect_signal(self.view.main_widget.column_middle.list, 'choice', self.handle_choice,
                             self.view.Columns.MIDDLE)
        urwid.connect_signal(self.view.main_widget.column_right.list, 'choice', self.handle_choice,
                             self.view.Columns.RIGHT)

        self.loop = urwid.MainLoop(
            self.view.main_widget_with_attr, self.view.palette, unhandled_input=self.handle_input)

    def run(self):
        self.loop.run()

    def show_all_or_exit_on_esc(self, key):
        if key == 'esc':
            is_item_selected = len(self.model.main_list) == 1
            is_filter_active = len(self.model.filter_string) > 0

            if self.model.filter_string != '':
                self.model.filter_string = ''

            if self.model.main_mode == Modes.NODES and (is_item_selected or is_filter_active):
                self.model.set_main_list(
                    self.model.graph.get_node_models(self.model.filter_string))
            elif self.model.main_mode == Modes.TOPICS and (is_item_selected or is_filter_active):
                self.model.set_main_list(
                    self.model.graph.get_topic_models(self.model.filter_string))
            elif self.model.main_mode != Modes.NODES_AND_TOPICS or is_filter_active:
                self.model.main_mode = Modes.NODES_AND_TOPICS
                self.model.set_main_list(self.model.graph.get_node_models(self.model.filter_string) +
                                         self.model.graph.get_topic_models(self.model.filter_string))
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
                self.handle_choice(None, None, selection,
                                   self.view.Columns.LEFT)
        elif key == 'right':
            selection = self.view.get_selection()
            if selection:
                self.handle_choice(None, None, selection,
                                   self.view.Columns.RIGHT)

    def update_filter(self, key):
        if isinstance(key, str) and key in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_/':
            self.model.filter_string = self.model.filter_string + key
            return True
        elif key == 'backspace':
            self.model.filter_string = self.model.filter_string[:-1]
            return True
        return False

    def handle_input(self, key):
        self.show_all_or_exit_on_esc(key)
        self.choose_on_arrow_out_of_view(key)
        if self.update_filter(key):
            if self.model.main_mode == Modes.NODES:
                self.model.set_main_list(
                    self.model.graph.get_node_models(self.model.filter_string))
            if self.model.main_mode == Modes.TOPICS:
                self.model.set_main_list(
                    self.model.graph.get_topic_models(self.model.filter_string))
            elif self.model.main_mode == Modes.NODES_AND_TOPICS:
                self.model.set_main_list(self.model.graph.get_node_models(self.model.filter_string) +
                                         self.model.graph.get_topic_models(self.model.filter_string))
            else:
                raise urwid.ExitMainLoop()

            self.view.main_widget.set_focus_column(
                self.view.Columns.MIDDLE.value)
            self.update_view()
        pass

    def handle_main_choice(self, choice):
        self.model.set_main_list([choice])
        self.model.set_input_list(choice.get_input())
        self.model.set_output_list(choice.get_output())

    def handle_choice(self, list, button, choice, column):
        self.model.choice = choice
        self.handle_main_choice(choice)
        if column == self.view.Columns.LEFT or column == self.view.Columns.RIGHT:
            pass
        elif column != self.view.Columns.MIDDLE:
            raise TypeError("column is neither left, right nor middle!")
        self.switch_mode()

        self.model.filter_string = ''
        self.update_view()
        self.view.set_focus(self.view.Columns.MIDDLE)

    def switch_mode(self):
        selection = self.view.get_selection()
        if isinstance(selection, model.NodeModel):
            self.model.main_mode = Modes.NODES
        elif isinstance(selection, model.TopicModel):
            self.model.main_mode = Modes.TOPICS
        else:
            raise RuntimeError(
                "current selection is neither node nor topic item!")

    def append_style(self, node_or_topic):
        if isinstance(node_or_topic, model.NodeModel):
            if node_or_topic.name == self.model.choice:
                return 'chosen_node', node_or_topic
            else:
                return 'node', node_or_topic
        elif isinstance(node_or_topic, model.TopicModel):
            if node_or_topic.name == self.model.choice:
                return 'chosen_topic', node_or_topic
            else:
                return 'topic', node_or_topic
        else:
            raise TypeError(
                "list entry is neither node nor topic: ", node_or_topic)

    def update_view(self):
        nodes_and_topics = [node for node in self.model.main_list]
        nodes_and_topics = [self.append_style(
            item) for item in nodes_and_topics]

        inputs = [self.append_style(item) for item in self.model.input_list]
        outputs = [self.append_style(item) for item in self.model.output_list]

        self.view.reset_list(inputs, self.view.Columns.LEFT)
        self.view.reset_list(nodes_and_topics, self.view.Columns.MIDDLE)
        self.view.reset_list(outputs, self.view.Columns.RIGHT)
        self.view.set_title(self.InputLabels[str(
            self.model.main_mode)] + ':', self.view.Columns.LEFT)
        self.view.set_title(self.MiddleLabels[str(
            self.model.main_mode)] + ':', self.view.Columns.MIDDLE)
        self.view.set_title(self.OutputLabels[str(
            self.model.main_mode)] + ':', self.view.Columns.RIGHT)
        self.view.set_footer(self.model.filter_string,
                             self.view.Columns.MIDDLE)


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
