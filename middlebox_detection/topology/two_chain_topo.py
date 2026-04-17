"""
Two-chain topology:
h1 --10-- rn1 --10-- rn2 --10-- r_mb1 --5-- rn3 --5-- r_mb2 --2-- rn4 --10-- h2
Bottleneck: r_mb2-rn4 at 2 Mbps
"""
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.node import Node


class LinuxRouter(Node):
    def config(self, mac=None, ip=None, defaultRoute=None, lo='up', **params):
        r = super().config(mac=mac, ip=ip, defaultRoute=defaultRoute, lo=lo, **params)
        self.cmd('sysctl -w net.ipv4.ip_forward=1')
        return r

    def terminate(self):
        self.cmd('sysctl -w net.ipv4.ip_forward=0')
        super().terminate()


def create_two_chain_topo():
    net = Mininet(controller=None, link=TCLink)

    h1    = net.addHost('h1',    ip='10.0.1.1/24',  defaultRoute='via 10.0.1.2')
    rn1   = net.addHost('rn1',   ip='10.0.1.2/24',  cls=LinuxRouter)
    rn2   = net.addHost('rn2',   ip='10.0.2.2/24',  cls=LinuxRouter)
    r_mb1 = net.addHost('r_mb1', ip='10.0.3.2/24',  cls=LinuxRouter)
    rn3   = net.addHost('rn3',   ip='10.0.4.2/24',  cls=LinuxRouter)
    r_mb2 = net.addHost('r_mb2', ip='10.0.5.2/24',  cls=LinuxRouter)
    rn4   = net.addHost('rn4',   ip='10.0.6.2/24',  cls=LinuxRouter)
    h2    = net.addHost('h2',    ip='10.0.7.2/24',  defaultRoute='via 10.0.7.1')

    net.addLink(h1,    rn1,   intfName1='h1-eth0',     intfName2='rn1-eth0',   bw=10, max_queue_size=100)
    net.addLink(rn1,   rn2,   intfName1='rn1-eth1',    intfName2='rn2-eth0',   bw=10, max_queue_size=100)
    net.addLink(rn2,   r_mb1, intfName1='rn2-eth1',    intfName2='r_mb1-eth0', bw=10, max_queue_size=100)
    net.addLink(r_mb1, rn3,   intfName1='r_mb1-eth1',  intfName2='rn3-eth0',   bw=5,  max_queue_size=50)
    net.addLink(rn3,   r_mb2, intfName1='rn3-eth1',    intfName2='r_mb2-eth0', bw=5,  max_queue_size=50)
    net.addLink(r_mb2, rn4,   intfName1='r_mb2-eth1',  intfName2='rn4-eth0',   bw=2,  max_queue_size=10)
    net.addLink(rn4,   h2,    intfName1='rn4-eth1',    intfName2='h2-eth0',    bw=10, max_queue_size=100)

    net.start()

    for node in [h1, rn1, rn2, r_mb1, rn3, r_mb2, rn4, h2]:
        for intf in node.intfList():
            if intf.name != 'lo':
                node.cmd(f'ip link set {intf.name} mtu 1500')

    # Additional IPs on router second interfaces
    rn1.cmd('ip addr add 10.0.2.1/24 dev rn1-eth1')
    rn2.cmd('ip addr add 10.0.3.1/24 dev rn2-eth1')
    r_mb1.cmd('ip addr add 10.0.4.1/24 dev r_mb1-eth1')
    rn3.cmd('ip addr add 10.0.5.1/24 dev rn3-eth1')
    r_mb2.cmd('ip addr add 10.0.6.1/24 dev r_mb2-eth1')
    rn4.cmd('ip addr add 10.0.7.1/24 dev rn4-eth1')

    # Static routes
    h1.cmd('ip route add default via 10.0.1.2')

    rn1.cmd('ip route add 10.0.3.0/24 via 10.0.2.2')
    rn1.cmd('ip route add 10.0.4.0/24 via 10.0.2.2')
    rn1.cmd('ip route add 10.0.5.0/24 via 10.0.2.2')
    rn1.cmd('ip route add 10.0.6.0/24 via 10.0.2.2')
    rn1.cmd('ip route add 10.0.7.0/24 via 10.0.2.2')

    rn2.cmd('ip addr add 10.0.2.2/24 dev rn2-eth0')
    rn2.cmd('ip route add 10.0.1.0/24 via 10.0.2.1')
    rn2.cmd('ip route add 10.0.4.0/24 via 10.0.3.2')
    rn2.cmd('ip route add 10.0.5.0/24 via 10.0.3.2')
    rn2.cmd('ip route add 10.0.6.0/24 via 10.0.3.2')
    rn2.cmd('ip route add 10.0.7.0/24 via 10.0.3.2')

    r_mb1.cmd('ip addr add 10.0.3.2/24 dev r_mb1-eth0')
    r_mb1.cmd('ip route add 10.0.1.0/24 via 10.0.3.1')
    r_mb1.cmd('ip route add 10.0.2.0/24 via 10.0.3.1')
    r_mb1.cmd('ip route add 10.0.5.0/24 via 10.0.4.2')
    r_mb1.cmd('ip route add 10.0.6.0/24 via 10.0.4.2')
    r_mb1.cmd('ip route add 10.0.7.0/24 via 10.0.4.2')

    rn3.cmd('ip addr add 10.0.4.2/24 dev rn3-eth0')
    rn3.cmd('ip route add 10.0.1.0/24 via 10.0.4.1')
    rn3.cmd('ip route add 10.0.2.0/24 via 10.0.4.1')
    rn3.cmd('ip route add 10.0.3.0/24 via 10.0.4.1')
    rn3.cmd('ip route add 10.0.6.0/24 via 10.0.5.2')
    rn3.cmd('ip route add 10.0.7.0/24 via 10.0.5.2')

    r_mb2.cmd('ip addr add 10.0.5.2/24 dev r_mb2-eth0')
    r_mb2.cmd('ip route add 10.0.1.0/24 via 10.0.5.1')
    r_mb2.cmd('ip route add 10.0.2.0/24 via 10.0.5.1')
    r_mb2.cmd('ip route add 10.0.3.0/24 via 10.0.5.1')
    r_mb2.cmd('ip route add 10.0.4.0/24 via 10.0.5.1')
    r_mb2.cmd('ip route add 10.0.7.0/24 via 10.0.6.2')

    rn4.cmd('ip addr add 10.0.6.2/24 dev rn4-eth0')
    rn4.cmd('ip route add 10.0.1.0/24 via 10.0.6.1')
    rn4.cmd('ip route add 10.0.2.0/24 via 10.0.6.1')
    rn4.cmd('ip route add 10.0.3.0/24 via 10.0.6.1')
    rn4.cmd('ip route add 10.0.4.0/24 via 10.0.6.1')
    rn4.cmd('ip route add 10.0.5.0/24 via 10.0.6.1')

    h2.cmd('ip route add default via 10.0.7.1')

    result = h1.cmd('ping -c 3 -W 2 10.0.7.2') or ''
    if '1 received' not in result and '2 received' not in result and '3 received' not in result:
        print('[WARN] h1 -> h2 ping failed in two_chain_topo')
    else:
        print('[OK] h1 -> h2 ping succeeded (two_chain)')

    return net, h1, h2, rn1, rn2, r_mb1, rn3, r_mb2, rn4
