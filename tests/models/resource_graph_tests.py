'''
ARCHES - a program developed to inventory and manage immovable cultural heritage.
Copyright (C) 2013 J. Paul Getty Trust and World Monuments Fund

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
'''

import os, json, uuid
from tests import test_settings
from tests.base_test import ArchesTestCase
from arches.management.commands.package_utils import resource_graphs
from arches.app.models import models
from arches.app.models.resource_graphs import ResourceGraph
from arches.app.utils.betterJSONSerializer import JSONSerializer


class ResourceGraphTests(ArchesTestCase):

    @classmethod
    def setUpClass(cls):
        resource_graphs.load_graphs(os.path.join(test_settings.RESOURCE_GRAPH_LOCATIONS))

        cls.NODE_NODETYPE_BRANCHMETADATAID = '22000000-0000-0000-0000-000000000001'
        cls.SINGLE_NODE_BRANCHMETADATAID = '22000000-0000-0000-0000-000000000000'
        cls.HERITAGE_RESOURCE_FIXTURE = 'd8f4db21-343e-4af3-8857-f7322dc9eb4b'

    @classmethod
    def tearDownClass(cls):
        root = models.Node.objects.get(pk=cls.HERITAGE_RESOURCE_FIXTURE)
        cls.deleteGraph(root)

    def setUp(self):
        newid = uuid.uuid1()
        newgroup = models.NodeGroup.objects.create(
            pk=newid,
            cardinality='1'
        )
        self.rootNode = models.Node.objects.create(
            pk=newid,
            name='ROOT NODE',
            description='Test Root Node',
            istopnode=True,
            ontologyclass='E1',
            datatype='semantic',
            nodegroup=newgroup
        )

    def tearDown(self):
        self.deleteGraph(self.rootNode)

    def test_graph_doesnt_polute_db(self):
        """
        test that the mere act of creating a ResourceGraph instance 
        doesn't save anything to the database

        """

        graph_obj = {
            'nodes':[{
                "status": None,
                "branchmetadataid": None,
                "description": "",
                "name": "ROOT_NODE",
                "istopnode": True,
                "ontologyclass": "",
                "nodeid": "55555555-343e-4af3-8857-f7322dc9eb4b",
                "nodegroupid": "55555555-343e-4af3-8857-f7322dc9eb4b",
                "datatype": "semantic",
                "cardinality": "1"
            },{
                "status": None,
                "branchmetadataid": None,
                "description": "",
                "name": "NODE_NAME",
                "istopnode": False,
                "ontologyclass": "",
                "nodeid": "66666666-24c9-4226-bde2-2c40ee60a26c",
                "nodegroupid": "55555555-343e-4af3-8857-f7322dc9eb4b",
                "datatype": "string",
                "cardinality": "n"
            }],
            'edges':[{
                "branchmetadataid": None,
                "rangenodeid": "66666666-24c9-4226-bde2-2c40ee60a26c",
                "name": "",
                "edgeid": "11111111-d50f-11e5-8754-80e6500ee4e4",
                "domainnodeid": "55555555-343e-4af3-8857-f7322dc9eb4b",
                "ontologyproperty": "P2",
                "description": ""
            }]
        }

        nodes_count_before = models.Node.objects.count()
        edges_count_before = models.Edge.objects.count()
        nodegroups_count_before = models.NodeGroup.objects.count()

        graph = ResourceGraph(graph_obj)

        self.assertEqual(models.Node.objects.count()-nodes_count_before, 0)
        self.assertEqual(models.Edge.objects.count()-edges_count_before, 0)
        self.assertEqual(models.NodeGroup.objects.count()-nodegroups_count_before, 0)

    def test_nodes_are_byref(self):
        """
        test that the nodes referred to in the ResourceGraph.edges are exact references to
        the nodes as opposed to a node with the same attribute values

        """

        graph = ResourceGraph(self.HERITAGE_RESOURCE_FIXTURE)

        node_mapping = {nodeid:id(node) for nodeid, node in graph.nodes.iteritems()}

        for key, edge in graph.edges.iteritems():
            self.assertEqual(node_mapping[edge.domainnode.pk], id(edge.domainnode))
            self.assertEqual(node_mapping[edge.rangenode.pk], id(edge.rangenode))

        for key, node in graph.nodes.iteritems():
            for key, edge in graph.edges.iteritems():
                newid = uuid.uuid4()
                if (edge.domainnode.pk == node.pk):
                    node.pk = newid
                    self.assertEqual(edge.domainnode.pk, newid)
                elif (edge.rangenode.pk == node.pk):
                    node.pk = newid
                    self.assertEqual(edge.rangenode.pk, newid)

    def test_copy_graph(self):
        """
        test that a copy of a graph has the same number of nodes and edges and that the primary keys have been changed
        and that the actual node references are different

        """

        graph = ResourceGraph(self.HERITAGE_RESOURCE_FIXTURE)
        graph_copy = graph.copy()

        self.assertEqual(len(graph.nodes), len(graph_copy.nodes))
        self.assertEqual(len(graph.edges), len(graph_copy.edges))
        self.assertEqual(len(graph.nodegroups), len(graph_copy.nodegroups))

        def findNodeByName(graph, name):
            for key, node in graph.nodes.iteritems():
                if node.name == name:
                    return node
            return None

        for key, node in graph.nodes.iteritems():
            node_copy = findNodeByName(graph_copy, node.name)
            self.assertIsNotNone(node_copy)
            self.assertNotEqual(node.pk, node_copy.pk)
            self.assertNotEqual(id(node), id(node_copy))
            if node.nodegroup != None:
                self.assertNotEqual(node.nodegroup, node_copy.nodegroup)
            
        for key, newedge in graph_copy.edges.iteritems():
            self.assertIsNotNone(graph_copy.nodes[newedge.domainnode_id])
            self.assertIsNotNone(graph_copy.nodes[newedge.rangenode_id])
            self.assertEqual(newedge.domainnode, graph_copy.nodes[newedge.domainnode.pk])
            self.assertEqual(newedge.rangenode, graph_copy.nodes[newedge.rangenode.pk])
            with self.assertRaises(KeyError):
                graph.edges[newedge.pk]

    def test_branch_append(self):
        """
        test if a branch is properly appended to a graph

        """

        nodes_count_before = models.Node.objects.count()
        edges_count_before = models.Edge.objects.count()
        nodegroups_count_before = models.NodeGroup.objects.count()

        graph = ResourceGraph(self.rootNode)
        graph.append_branch('P1', branchmetadataid=self.NODE_NODETYPE_BRANCHMETADATAID)
        graph.save()

        self.assertEqual(len(graph.nodes), 3)
        self.assertEqual(len(graph.edges), 2)
        self.assertEqual(len(graph.nodegroups), 2)

        self.assertEqual(models.Node.objects.count()-nodes_count_before, 2)
        self.assertEqual(models.Edge.objects.count()-edges_count_before, 2)
        self.assertEqual(models.NodeGroup.objects.count()-nodegroups_count_before, 1)

        for key, edge in graph.edges.iteritems():
            self.assertIsNotNone(graph.nodes[edge.domainnode_id])
            self.assertIsNotNone(graph.nodes[edge.rangenode_id])
            self.assertEqual(edge.domainnode, graph.nodes[edge.domainnode.pk])
            self.assertEqual(edge.rangenode, graph.nodes[edge.rangenode.pk])

        for key, node in graph.nodes.iteritems():
            if node.istopnode:
                self.assertEqual(node, self.rootNode)


        appended_branch = graph.append_branch('P1', branchmetadataid=self.SINGLE_NODE_BRANCHMETADATAID)
        graph.save()
        self.assertEqual(len(graph.nodes), 4)
        self.assertEqual(len(graph.edges), 3)
        self.assertEqual(len(graph.nodegroups), 2)

        self.assertEqual(models.Node.objects.count()-nodes_count_before, 3)
        self.assertEqual(models.Edge.objects.count()-edges_count_before, 3)
        self.assertEqual(models.NodeGroup.objects.count()-nodegroups_count_before, 1)

        self.assertEqual(appended_branch.root.nodegroup,self.rootNode.nodegroup)

    def test_make_tree(self):
        graph = ResourceGraph(self.HERITAGE_RESOURCE_FIXTURE)
