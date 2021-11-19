from enum import Enum

import rosnode
import rosgraph


ID = '/rosgraph_tui'


class ListEntryTypes(Enum):
    NODE = 0
    TOPIC = 1


class Model:
    def __init__(self):
        self.graph = GraphModel()

        self.input_list = []
        self.main_list = nodes_from_names(self.graph, self.graph.get_nodes()) + \
            topics_from_names(self.graph, self.graph.get_topics())
        self.output_list = []
        self.filter_string = ''
        self.choice = ''

    def set_main_list(self, items):
        self.main_list = items

    def set_input_list(self, items):
        self.input_list = items

    def set_output_list(self, items):
        self.output_list = items


class NodeModel:
    def __init__(self, name, graph):
        self.name = name
        self.graph = graph

    def name_string(self):
        return "N " + self.name

    def info_string(self):
        return ''

    def get_input(self):
        return topics_from_names(self.graph, self.graph.get_subscriptions(self.name))

    def get_output(self):
        return topics_from_names(self.graph, self.graph.get_publications(self.name))


class TopicModel:
    def __init__(self, name, graph):
        self.name = name
        self.graph = graph
        self.topic_type = graph.topic_type(name)

    def name_string(self):
        return "T " + self.name

    def info_string(self):
        return 'Type: ' + self.topic_type

    def get_input(self):
        return nodes_from_names(self.graph, self.graph.get_publishers(self.name))

    def get_output(self):
        return nodes_from_names(self.graph, self.graph.get_subscribers(self.name))


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

    def get_node_models(self, filter_string=''):
        return nodes_from_names(self, self.get_nodes(filter_string))

    def get_topics(self, filter_string=''):
        return [item for item in sorted(t for t, l in self.all_topics) if filter_string in item]

    def get_topic_models(self, filter_string=''):
        return topics_from_names(self, self.get_topics(filter_string))

    def get_publishers(self, topic_name):
        matches = [l for t, l in self.all_pubs if topic_name == t]
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


def nodes_from_names(graph, names):
    return [NodeModel(name, graph) for name in names]


def topics_from_names(graph, names):
    return [TopicModel(name, graph) for name in names]
