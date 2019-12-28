from enum import Enum

import rosnode
import rosgraph


ID = '/rosgraph_tui'


class Model:
    ListEntryTypes = Enum('NODE', 'TOPIC')

    def __init__(self):
        self.graph = GraphModel()

        self.input_list = []
        self.main_node_list = []
        self.main_topic_list = []
        self.output_list = []

        self.set_main_node_list(self.graph.get_nodes())
        self.set_main_topic_list(self.graph.get_topics())

    def set_list(self, list, items, item_type=None):
        del list[:]
        if items:
            if item_type == self.ListEntryTypes.NODE:
                for item in items:
                    list.append(NodeModel(item))
            elif item_type == self.ListEntryTypes.TOPIC:
                for item in items:
                    list.append(TopicModel(item))
            else:
                raise TypeError("list entry is neither node nor topic: " + str(item_type))

    def set_input_list(self, items, item_type=None):
        self.set_list(self.input_list, items, item_type)

    def set_output_list(self, items, item_type=None):
        self.set_list(self.output_list, items, item_type)

    def set_main_node_list(self, items):
        self.set_list(self.main_node_list, items, self.ListEntryTypes.NODE)

    def set_main_topic_list(self, items):
        self.set_list(self.main_topic_list, items, self.ListEntryTypes.TOPIC)


class NodeModel:
    def __init__(self, name):
        self.name = name


class TopicModel:
    def __init__(self, name):
        self.name = name


class GraphModel:
    def __init__(self):
        self.all_nodes = rosnode.get_node_names()

        master = rosgraph.Master(ID)
        try:
            state = master.getSystemState()
            self.all_topics = master.getPublishedTopics('/')
        except socket.error:
            raise ROSNodeIOException("Unable to communicate with master!")
        self.all_pubs = state[0]
        self.all_subs = state[1]

    def get_nodes(self, filter_string=''):
        return [item for item in sorted(self.all_nodes) if filter_string in item]

    def get_topics(self, filter_string=''):
        return [item for item in sorted(t for t, l in self.all_topics) if filter_string in item]

    def get_publishers(self, topic_name):
        matches = [l for t, l in self.all_pubs if topic_name==t]
        if matches:
            return sorted(*matches)
        else:
            return []

    def get_subscribers(self, topic_name):
        matches = [l for t, l in self.all_subs if topic_name == t]
        if matches:
            return sorted(*matches)
        else:
            return []

    def get_publications(self, node_name):
        return sorted([t for t, l in self.all_pubs if node_name in l])

    def get_subscriptions(self, node_name):
        return sorted([t for t, l in self.all_subs if node_name in l])

    def topic_type(self, t):
        matches = [t_type for t_name, t_type in self.all_topics if t_name == t]
        if matches:
            return matches[0]
        return 'unknown type'
