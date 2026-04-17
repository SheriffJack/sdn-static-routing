#!/usr/bin/env python3
"""
Static Routing Topology - SDN Mininet Project
Topology:
    h1 --- s1 --- s2 --- s3 --- h3
                   |
                  h2

    Hosts: h1 (10.0.0.1), h2 (10.0.0.2), h3 (10.0.0.3)
    Switches: s1, s2, s3
    Static routes are installed by the Ryu controller.
"""

from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink


def create_topology():
    """Create and start the Mininet topology."""

    net = Mininet(
        controller=RemoteController,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True
    )

    info("*** Adding controller (Ryu running on localhost:6633)\n")
    c0 = net.addController(
        'c0',
        controller=RemoteController,
        ip='127.0.0.1',
        port=6633
    )

    info("*** Adding switches\n")
    s1 = net.addSwitch('s1', protocols='OpenFlow10')
    s2 = net.addSwitch('s2', protocols='OpenFlow10')
    s3 = net.addSwitch('s3', protocols='OpenFlow10')

    info("*** Adding hosts\n")
    h1 = net.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
    h2 = net.addHost('h2', ip='10.0.0.2/24', mac='00:00:00:00:00:02')
    h3 = net.addHost('h3', ip='10.0.0.3/24', mac='00:00:00:00:00:03')

    info("*** Adding links\n")
    # Host to switch links
    net.addLink(h1, s1)   # h1-eth0 <-> s1-eth1
    net.addLink(h2, s2)   # h2-eth0 <-> s2-eth1
    net.addLink(h3, s3)   # h3-eth0 <-> s3-eth1

    # Switch to switch links
    net.addLink(s1, s2)   # s1-eth2 <-> s2-eth2
    net.addLink(s2, s3)   # s2-eth3 <-> s3-eth2

    info("*** Starting network\n")
    net.start()

    info("*** Verifying switch connections\n")
    for switch in [s1, s2, s3]:
        info(f"    {switch.name} ports: {switch.intfNames()}\n")

    info("\n*** Topology Ready ***\n")
    info("    h1 (10.0.0.1) --- s1 --- s2 --- s3 --- h3 (10.0.0.3)\n")
    info("                              |              \n")
    info("                         h2 (10.0.0.2)      \n\n")

    info("*** Waiting for Ryu controller to install flow rules...\n")
    info("    Run 'pingall' to test connectivity.\n")
    info("    Run 'h1 ping h3' to test static path h1->s1->s2->s3->h3\n")
    info("    Use 'sh ovs-ofctl dump-flows s1' to inspect flow tables.\n\n")

    CLI(net)

    info("*** Stopping network\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    create_topology()
