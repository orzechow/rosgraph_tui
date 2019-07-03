import rosnode
import rosgraph


ID = '/rosgraph_tui'


class Model:
    def __init__(self):
        self.graph = GraphModel()

        self.input_list = ''
        self.main_node_list = self.graph.get_nodes()
        self.main_topic_list = self.graph.get_topics()
        self.output_list = ''


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

    def get_nodes(self, fuzzyname=''):
        return sorted(self.all_nodes)

    def get_topics(self, fuzzyname=''):
        return sorted(t for t, l in self.all_topics)

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
