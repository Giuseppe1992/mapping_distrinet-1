import itertools
import logging
import random
import warnings

import networkx as nx


class VirtualNetwork(object):

    def __init__(self, g):
        """Initialize the virtual network with the graph g."""
        self._g = g
        self._log = logging.getLogger(__name__)

    @property
    def g(self):
        return self._g

    @g.setter
    def g(self, g_new):
        warnings.warn("original virtual network has been modified")
        self._g = g_new

    def edges(self):
        """Return the edges of the graph."""
        return self._g.edges()

    def sorted_edges(self):
        """Return the edges of the graph sorted in lexicographic way."""
        if not hasattr(self, '_sorted_links'):
            self._sorted_links = set((u, v) if u < v else (v, u) for (u, v) in self.edges())
        return self._sorted_links

    def sorted_edges_from(self, i):
        """Return the edges starting at node i with each edge sorted in lexicographic way."""
        if not hasattr(self, '_links_from'):
            self._links_from = {}
        try:
            return self._links_from[i]
        except KeyError:
            res = self._links_from[i] = set((i, j) if i < j else (j, i) for j in self._g[i])
        return res

    def nodes(self):
        """Return the nodes of the graph."""
        return self._g.nodes()

    def number_of_nodes(self):
        """Return the number of nodes."""
        return self._g.number_of_nodes()

    def req_cores(self, node):
        """Return the required cores for a virtual node."""
        return self._g.node[node]['cores']

    def req_memory(self, node):
        """Return the required amount of memory for a virtual node."""
        return self._g.node[node]['memory']

    def req_rate(self, i, j):
        """Return the required link rate for a virtual link"""
        return self._g[i][j]['rate']

    def neighbors(self, i):
        """Return the neighbors of a node."""
        return self._g[i]

    @classmethod
    def create_fat_tree(cls, k=2, density=2, node_req_cores=2, node_req_memory=8000, link_req_rate=200):
        """create a K-ary FatTree with host density set to density.

           Each node is assigned to a request of *node_req_cores* CPU cores
           and *node_req_memory* Mib of Ram.
           Each link is assigned to a request of *link_req_rate* Mbps.
        """
        assert k > 1, "k should be greater than 1"
        assert not k % 2, "k should be divisible by 2"
        assert float(node_req_cores).is_integer(), "the number of requested cores should be integer"
        assert node_req_cores >= 0, "node CPU cores cannot be negative"
        assert node_req_memory >= 0, "node memory cannot be negative"
        assert link_req_rate >= 0, "link rate cannot be negative"

        n_pods = k
        n_core_switches = int((k / 2) ** 2)
        n_aggr_switches = n_edge_switches = int(k * k / 2)
        n_hosts = n_edge_switches * density

        hosts = [f'host_{i}' for i in range(1, n_hosts + 1)]
        core_switches = [f'core_{i}' for i in range(1, n_core_switches + 1)]
        aggr_switches = [f'aggr_{i}' for i in range(1, n_aggr_switches + 1)]
        edge_switches = [f'edge_{i}' for i in range(1, n_edge_switches + 1)]

        g = nx.Graph()
        g.add_nodes_from(itertools.chain(hosts, core_switches, aggr_switches, edge_switches), cores=node_req_cores,
                         memory=node_req_memory)

        # Core to Aggr
        end = int(n_pods / 2)
        for x in range(0, n_aggr_switches, end):
            for i in range(0, end):
                for j in range(0, end):
                    g.add_edge(core_switches[i * end + j], aggr_switches[x + i], rate=link_req_rate)

        # Aggr to Edge
        for x in range(0, n_aggr_switches, end):
            for i in range(0, end):
                for j in range(0, end):
                    g.add_edge(aggr_switches[x + i], edge_switches[x + j], rate=link_req_rate)

        # Edge to Host
        for x in range(0, n_edge_switches):
            for i in range(density):
                g.add_edge(edge_switches[x], hosts[density * x + i], rate=link_req_rate)

        return cls(nx.freeze(g))

    @classmethod
    def create_random_EC2(cls, n_nodes=100, seed=99):
        """create a random EC2 instance."""
        random.seed(seed)
        range_cores = list(range(1, 11))
        range_memory = list(range(512, 4096, 512))

        g = nx.Graph()
        g.add_nodes_from(
            ((n, dict(cores=random.choice(range_cores), memory=random.choice(range_memory))) for n in range(n_nodes)))
        return cls(nx.freeze(g))

    @classmethod
    def create_random_nw(cls, n_nodes=10, p=0.15, node_req_cores=2, node_req_memory=8000, link_req_rate=200, seed=99):
        """create a random network."""
        g = nx.gnp_random_graph(n_nodes, p=p, seed=seed, directed=False)
        for (u, v) in g.edges():
            g[u][v]['rate'] = link_req_rate
        for u in g.nodes():
            g.nodes[u]['cores'] = node_req_cores
            g.nodes[u]['memory'] = node_req_memory
        return cls(nx.freeze(g))

    @classmethod
    def read_from_file(cls, filename):
        """Read the graph from a file"""
        raise NotImplementedError

    @classmethod
    def from_mininet(cls, mininet_topo):
        from mininet.topo import Topo

        assert isinstance(mininet_topo, Topo), "Invalid Network Format"

        g = nx.Graph()

        for u in mininet_topo.nodes():
            g.add_node(u, cores=mininet_topo.nodeInfo(u).get('cores', 0),
                       memory=mininet_topo.nodeInfo(u).get('memory', 0))

        for (u, v) in mininet_topo.iterLinks(withInfo=False):
            g.add_edge(u, v, rate=mininet_topo.linkInfo(u, v).get('rate', 0))

        return cls(nx.freeze(g))
