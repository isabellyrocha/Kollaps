import xml.etree.ElementTree as ET
from random import choice, randint
from string import ascii_letters

from utils import fail
from NetGraph import NetGraph


class XMLGraphParser:
    def __init__(self, file, graph):
        self.file = file
        self.graph = graph  # type: NetGraph

    def parse_services(self, root):
        for service in root:
            if service.tag != 'service':
                fail('Invalid tag inside <services>: ' + service.tag)
            if 'name' not in service.attrib or 'image' not in service.attrib:
                fail('A service needs a name and an image attribute.')
            if not service.attrib['name'] or not service.attrib['image']:
                fail('A service needs a name and an image attribute.')

            replicas = 1
            if 'replicas' in service.attrib:
                try:
                    replicas = int(service.attrib['replicas'])
                except:
                    fail('replicas attribute must be a valid integer.')

            command = None
            if 'command' in service.attrib:
                command = service.attrib['command']

            shared = False
            if 'share' in service.attrib:
                shared = (service.attrib['share'] == "true")

            for i in range(replicas):
                    self.graph.new_service(service.attrib['name'], service.attrib['image'], command, shared)

    def parse_bridges(self, root):
        for bridge in root:
            if bridge.tag != 'bridge':
                fail('Invalid tag inside <bridges>: ' + bridge.tag)
            if 'name' not in bridge.attrib:
                fail('A bridge needs to have a name.')
            if not bridge.attrib['name']:
                fail('A bridge needs to have a name.')
            self.graph.new_bridge(bridge.attrib['name'])

    def create_meta_bridge(self):
        while True:  # do-while loop
            meta_bridge_name = "".join(choice(ascii_letters) for x in range(randint(128, 128)))
            if len(self.graph.get_nodes(meta_bridge_name)) == 0:
                break
        self.graph.new_bridge(meta_bridge_name)
        return meta_bridge_name

    def parse_links(self, root):
        for link in root:
            if link.tag != 'link':
                fail('Invalid tag inside <links>: ' + link.tag)
            if 'origin' not in link.attrib or 'dest' not in link.attrib or 'latency' not in link.attrib or \
                    'drop' not in link.attrib or 'upload' not in link.attrib or 'download' not in link.attrib or \
                    'network' not in link.attrib:
                fail("Incomplete link description.")

            source_nodes = self.graph.get_nodes(link.attrib['origin'])
            destination_nodes = self.graph.get_nodes(link.attrib['dest'])

            both_shared = (source_nodes[0].shared_link and destination_nodes[0].shared_link)
            if both_shared:
                src_meta_bridge = self.create_meta_bridge()
                dst_meta_bridge = self.create_meta_bridge()
                # create a link between both meta bridges
                self.graph.new_link(src_meta_bridge, dst_meta_bridge, link.attrib['latency'],
                                    link.attrib['drop'], link.attrib['upload'], link.attrib['network'])
                self.graph.new_link(dst_meta_bridge, src_meta_bridge, link.attrib['latency'],
                                    link.attrib['drop'], link.attrib['download'], link.attrib['network'])
                # connect source to src meta bridge
                self.graph.new_link(link.attrib['origin'], src_meta_bridge, 0,
                                    0.0, link.attrib['upload'], link.attrib['network'])
                self.graph.new_link(src_meta_bridge, link.attrib['origin'], 0,
                                    0.0, link.attrib['download'], link.attrib['network'])
                # connect destination to dst meta bridge
                self.graph.new_link(dst_meta_bridge, link.attrib['dest'], 0,
                                    0.0, link.attrib['upload'], link.attrib['network'])
                self.graph.new_link(link.attrib['dest'], dst_meta_bridge, 0,
                                    0.0, link.attrib['download'], link.attrib['network'])
            elif source_nodes[0].shared_link:
                meta_bridge = self.create_meta_bridge()
                # create a link between meta bridge and destination
                self.graph.new_link(meta_bridge, link.attrib['dest'], link.attrib['latency'],
                                    link.attrib['drop'], link.attrib['upload'], link.attrib['network'])
                self.graph.new_link(link.attrib['dest'], meta_bridge, link.attrib['latency'],
                                    link.attrib['drop'], link.attrib['download'], link.attrib['network'])
                # connect origin to meta bridge
                self.graph.new_link(link.attrib['origin'], meta_bridge, 0,
                                    0.0, link.attrib['upload'], link.attrib['network'])
                self.graph.new_link(meta_bridge, link.attrib['origin'], 0,
                                    0.0, link.attrib['download'], link.attrib['network'])
            elif destination_nodes[0].shared_link:
                meta_bridge = self.create_meta_bridge()
                # create a link between origin and meta_bridge
                self.graph.new_link(link.attrib['origin'], meta_bridge, link.attrib['latency'],
                                    link.attrib['drop'], link.attrib['upload'], link.attrib['network'])
                self.graph.new_link(meta_bridge, link.attrib['origin'], link.attrib['latency'],
                                    link.attrib['drop'], link.attrib['download'], link.attrib['network'])
                # connect meta bridge to destination
                self.graph.new_link(meta_bridge, link.attrib['dest'], 0,
                                    0.0, link.attrib['upload'], link.attrib['network'])
                self.graph.new_link(link.attrib['dest'], meta_bridge, 0,
                                    0.0, link.attrib['download'], link.attrib['network'])
            else:
                # Regular case create a link between origin and destination
                self.graph.new_link(link.attrib['origin'], link.attrib['dest'], link.attrib['latency'],
                                link.attrib['drop'], link.attrib['upload'], link.attrib['network'])
                self.graph.new_link(link.attrib['dest'], link.attrib['origin'], link.attrib['latency'],
                                link.attrib['drop'], link.attrib['download'], link.attrib['network'])

    def fill_graph(self):
        XMLtree = ET.parse(self.file)
        root = XMLtree.getroot()
        if root.tag != 'experiment':
            fail('Not a valid NEED topology file, root is not <experiment>')

        services = None
        bridges = None
        links = None
        for child in root:
            if child.tag == 'services':
                if services is not None:
                    fail("Only one <services> block is allowed.")
                services = child
            elif child.tag == 'bridges':
                if bridges is not None:
                    fail("Only one <bridges> block is allowed.")
                bridges = child
            elif child.tag == 'links':
                if links is not None:
                    fail("Only one <links> block is allowed.")
                links = child
            else:
                fail('Unknown tag: ' + child.tag)

        # Links must be parsed last
        if services is None:
            fail("No services declared in topology description")
        self.parse_services(services)
        if bridges is not None:
            self.parse_bridges(bridges)
        if links is None:
            fail("No links declared in topology descritpion")
        self.parse_links(links)
