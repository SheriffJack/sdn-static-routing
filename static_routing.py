"""
Static Routing Controller - POX Version
========================================
Place this file inside ~/pox/ext/ and run with:
    python3 pox.py static_routing --verbose

Topology:
    h1 (10.0.0.1) --- s1 --- s2 --- s3 --- h3 (10.0.0.3)
                               |
                          h2 (10.0.0.2)

Port mapping:
    s1: port 1 = h1,  port 2 = s2
    s2: port 1 = h2,  port 2 = s1,  port 3 = s3
    s3: port 1 = h3,  port 2 = s2
"""

from pox.core import core
from pox.lib.util import dpidToStr
import pox.openflow.libopenflow_01 as of
from pox.lib.addresses import IPAddr, EthAddr
from pox.lib.packet import ethernet, arp, ipv4

log = core.getLogger()

# ---------------------------------------------------------------------------
# Static IP routing table
# (dpid, ip_src, ip_dst) -> out_port
# ---------------------------------------------------------------------------
STATIC_ROUTES = {
    # s1 (dpid=1)
    (1, '10.0.0.1', '10.0.0.2'): 2,
    (1, '10.0.0.1', '10.0.0.3'): 2,
    (1, '10.0.0.2', '10.0.0.1'): 1,
    (1, '10.0.0.3', '10.0.0.1'): 1,

    # s2 (dpid=2)
    (2, '10.0.0.1', '10.0.0.2'): 1,
    (2, '10.0.0.1', '10.0.0.3'): 3,
    (2, '10.0.0.2', '10.0.0.1'): 2,
    (2, '10.0.0.2', '10.0.0.3'): 3,
    (2, '10.0.0.3', '10.0.0.1'): 2,
    (2, '10.0.0.3', '10.0.0.2'): 1,

    # s3 (dpid=3)
    (3, '10.0.0.1', '10.0.0.3'): 1,
    (3, '10.0.0.2', '10.0.0.3'): 1,
    (3, '10.0.0.3', '10.0.0.1'): 2,
    (3, '10.0.0.3', '10.0.0.2'): 2,
}

# ARP routing table
# (dpid, target_ip) -> out_port
ARP_ROUTES = {
    (1, '10.0.0.1'): 1,
    (1, '10.0.0.2'): 2,
    (1, '10.0.0.3'): 2,

    (2, '10.0.0.1'): 2,
    (2, '10.0.0.2'): 1,
    (2, '10.0.0.3'): 3,

    (3, '10.0.0.1'): 2,
    (3, '10.0.0.2'): 2,
    (3, '10.0.0.3'): 1,
}


class StaticRoutingController(object):

    def __init__(self):
        core.openflow.addListeners(self)
        log.info("StaticRoutingController started. Waiting for switches...")

    # ------------------------------------------------------------------
    # Switch connects → install all static flow rules immediately
    # ------------------------------------------------------------------
    def _handle_ConnectionUp(self, event):
        dpid = event.dpid
        connection = event.connection
        log.info(f"Switch connected: dpid={dpid}")

        # Install table-miss rule first (send unknown packets to controller)
        self._install_table_miss(connection)

        # Install all static IP flow rules for this switch
        count = 0
        for (sw_id, ip_src, ip_dst), out_port in STATIC_ROUTES.items():
            if sw_id != dpid:
                continue

            msg = of.ofp_flow_mod()
            msg.priority = 10
            msg.idle_timeout = 0   # never expire
            msg.hard_timeout = 0   # never expire

            # Match: IPv4, specific src and dst IP
            msg.match.dl_type = 0x0800       # IPv4 ethertype
            msg.match.nw_src = IPAddr(ip_src)
            msg.match.nw_dst = IPAddr(ip_dst)

            # Action: output to port
            msg.actions.append(of.ofp_action_output(port=out_port))

            connection.send(msg)
            count += 1
            log.info(f"  Static rule dpid={dpid}: {ip_src} -> {ip_dst} => port {out_port}")

        log.info(f"  Total rules installed on dpid={dpid}: {count}")

    def _install_table_miss(self, connection):
        """Send unmatched packets to controller."""
        msg = of.ofp_flow_mod()
        msg.priority = 0
        msg.actions.append(of.ofp_action_output(port=of.OFPP_CONTROLLER))
        connection.send(msg)

    # ------------------------------------------------------------------
    # packet_in: handle ARP and any unmatched IPv4
    # ------------------------------------------------------------------
    def _handle_PacketIn(self, event):
        dpid = event.dpid
        in_port = event.port
        pkt = event.parsed

        if not pkt.parsed:
            return

        # --- Handle ARP ---
        arp_pkt = pkt.find('arp')
        if arp_pkt:
            target_ip = str(arp_pkt.protodst)
            key = (dpid, target_ip)

            if key in ARP_ROUTES:
                out_port = ARP_ROUTES[key]
                if out_port == in_port:
                    return
                log.info(f"ARP dpid={dpid}: target={target_ip} => port {out_port}")
                self._send_packet(event, out_port)
            else:
                # Flood as fallback for ARP
                log.warning(f"Unknown ARP target {target_ip} on dpid={dpid}. Flooding.")
                self._send_packet(event, of.OFPP_FLOOD)
            return

        # --- Handle IPv4 fallback ---
        ip_pkt = pkt.find('ipv4')
        if ip_pkt:
            ip_src = str(ip_pkt.srcip)
            ip_dst = str(ip_pkt.dstip)
            key = (dpid, ip_src, ip_dst)

            if key in STATIC_ROUTES:
                out_port = STATIC_ROUTES[key]
                log.warning(f"packet_in fallback dpid={dpid}: {ip_src}->{ip_dst} => port {out_port}")
                self._send_packet(event, out_port)
            else:
                log.warning(f"No route for dpid={dpid} {ip_src}->{ip_dst}. Dropping.")

    def _send_packet(self, event, out_port):
        msg = of.ofp_packet_out()
        msg.data = event.ofp
        msg.in_port = event.port
        msg.actions.append(of.ofp_action_output(port=out_port))
        event.connection.send(msg)


def launch():
    core.registerNew(StaticRoutingController)
    log.info("Static Routing Controller launched.")
