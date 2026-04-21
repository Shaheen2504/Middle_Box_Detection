"""
Three-chain topology:
h1 --10-- rn1 --10-- rn2 --10-- r_mb1 --5-- rn3 --5-- r_mb2 --5-- rn4 --5-- r_mb3 --2-- rn5 --10-- h2
Bottleneck: r_mb3-rn5 at 2 Mbps
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


def create_three_chain_topo():
    net = Mininet(controller=None, link=TCLink)

    h1    = net.addHost('h1',    ip='10.0.1.1/24',  defaultRoute='via 10.0.1.2')
    rn1   = net.addHost('rn1',   ip='10.0.1.2/24',  cls=LinuxRouter)
    rn2   = net.addHost('rn2',   ip='10.0.2.2/24',  cls=LinuxRouter)
    r_mb1 = net.addHost('r_mb1', ip='10.0.3.2/24',  cls=LinuxRouter)
    rn3   = net.addHost('rn3',   ip='10.0.4.2/24',  cls=LinuxRouter)
    r_mb2 = net.addHost('r_mb2', ip='10.0.5.2/24',  cls=LinuxRouter)
    rn4   = net.addHost('rn4',   ip='10.0.6.2/24',  cls=LinuxRouter)
    r_mb3 = net.addHost('r_mb3', ip='10.0.7.2/24',  cls=LinuxRouter)
    rn5   = net.addHost('rn5',   ip='10.0.8.2/24',  cls=LinuxRouter)
    h2    = net.addHost('h2',    ip='10.0.9.2/24',  defaultRoute='via 10.0.9.1')

    net.addLink(h1,    rn1,   intfName1='h1-eth0',     intfName2='rn1-eth0',   bw=10, max_queue_size=100)
    net.addLink(rn1,   rn2,   intfName1='rn1-eth1',    intfName2='rn2-eth0',   bw=10, max_queue_size=100)
    net.addLink(rn2,   r_mb1, intfName1='rn2-eth1',    intfName2='r_mb1-eth0', bw=10, max_queue_size=100)
    net.addLink(r_mb1, rn3,   intfName1='r_mb1-eth1',  intfName2='rn3-eth0',   bw=5,  max_queue_size=50)
    net.addLink(rn3,   r_mb2, intfName1='rn3-eth1',    intfName2='r_mb2-eth0', bw=5,  max_queue_size=50)
    net.addLink(r_mb2, rn4,   intfName1='r_mb2-eth1',  intfName2='rn4-eth0',   bw=5,  max_queue_size=50)
    net.addLink(rn4,   r_mb3, intfName1='rn4-eth1',    intfName2='r_mb3-eth0', bw=5,  max_queue_size=50)
    net.addLink(r_mb3, rn5,   intfName1='r_mb3-eth1',  intfName2='rn5-eth0',   bw=2,  max_queue_size=10)
    net.addLink(rn5,   h2,    intfName1='rn5-eth1',    intfName2='h2-eth0',    bw=10, max_queue_size=100)

    net.start()

    for node in [h1, rn1, rn2, r_mb1, rn3, r_mb2, rn4, r_mb3, rn5, h2]:
        for intf in node.intfList():
            if intf.name != 'lo':
                node.cmd(f'ip link set {intf.name} mtu 1500')

    # Additional IPs
    rn1.cmd('ip addr add 10.0.2.1/24 dev rn1-eth1')
    rn2.cmd('ip addr add 10.0.3.1/24 dev rn2-eth1')
    r_mb1.cmd('ip addr add 10.0.4.1/24 dev r_mb1-eth1')
    rn3.cmd('ip addr add 10.0.5.1/24 dev rn3-eth1')
    r_mb2.cmd('ip addr add 10.0.6.1/24 dev r_mb2-eth1')
    rn4.cmd('ip addr add 10.0.7.1/24 dev rn4-eth1')
    r_mb3.cmd('ip addr add 10.0.8.1/24 dev r_mb3-eth1')
    rn5.cmd('ip addr add 10.0.9.1/24 dev rn5-eth1')

    subnets = [f'10.0.{i}.0/24' for i in range(1, 10)]

    def add_routes(node, via_fwd, via_bk, fwd_nets, bk_nets):
        for net_addr in fwd_nets:
            node.cmd(f'ip route add {net_addr} via {via_fwd}')
        for net_addr in bk_nets:
            node.cmd(f'ip route add {net_addr} via {via_bk}')

    h1.cmd('ip route add default via 10.0.1.2')
    h2.cmd('ip route add default via 10.0.9.1')

    # rn1: eth0=10.0.1.x, eth1=10.0.2.x
    rn2.cmd('ip addr add 10.0.2.2/24 dev rn2-eth0')
    r_mb1.cmd('ip addr add 10.0.3.2/24 dev r_mb1-eth0')
    rn3.cmd('ip addr add 10.0.4.2/24 dev rn3-eth0')
    r_mb2.cmd('ip addr add 10.0.5.2/24 dev r_mb2-eth0')
    rn4.cmd('ip addr add 10.0.6.2/24 dev rn4-eth0')
    r_mb3.cmd('ip addr add 10.0.7.2/24 dev r_mb3-eth0')
    rn5.cmd('ip addr add 10.0.8.2/24 dev rn5-eth0')

    # rn1: knows subnet 1 on eth0, 2 on eth1; forward 3-9 via 10.0.2.2
    for i in range(3, 10):
        rn1.cmd(f'ip route add 10.0.{i}.0/24 via 10.0.2.2')
    rn1.cmd('ip route add 10.0.1.0/24 dev rn1-eth0')

    # rn2
    rn2.cmd('ip route add 10.0.1.0/24 via 10.0.2.1')
    for i in range(4, 10):
        rn2.cmd(f'ip route add 10.0.{i}.0/24 via 10.0.3.2')

    # r_mb1
    r_mb1.cmd('ip route add 10.0.1.0/24 via 10.0.3.1')
    r_mb1.cmd('ip route add 10.0.2.0/24 via 10.0.3.1')
    for i in range(5, 10):
        r_mb1.cmd(f'ip route add 10.0.{i}.0/24 via 10.0.4.2')

    # rn3
    rn3.cmd('ip route add 10.0.1.0/24 via 10.0.4.1')
    rn3.cmd('ip route add 10.0.2.0/24 via 10.0.4.1')
    rn3.cmd('ip route add 10.0.3.0/24 via 10.0.4.1')
    for i in range(6, 10):
        rn3.cmd(f'ip route add 10.0.{i}.0/24 via 10.0.5.2')

    # r_mb2
    for i in range(1, 5):
        r_mb2.cmd(f'ip route add 10.0.{i}.0/24 via 10.0.5.1')
    for i in range(7, 10):
        r_mb2.cmd(f'ip route add 10.0.{i}.0/24 via 10.0.6.2')

    # rn4
    for i in range(1, 6):
        rn4.cmd(f'ip route add 10.0.{i}.0/24 via 10.0.6.1')
    for i in range(8, 10):
        rn4.cmd(f'ip route add 10.0.{i}.0/24 via 10.0.7.2')

    # r_mb3
    for i in range(1, 7):
        r_mb3.cmd(f'ip route add 10.0.{i}.0/24 via 10.0.7.1')
    r_mb3.cmd('ip route add 10.0.9.0/24 via 10.0.8.2')

    # rn5
    for i in range(1, 8):
        rn5.cmd(f'ip route add 10.0.{i}.0/24 via 10.0.8.1')

    result = h1.cmd('ping -c 3 -W 2 10.0.9.2') or ''
    if '1 received' not in result and '2 received' not in result and '3 received' not in result:
        print('[WARN] h1 -> h2 ping failed in three_chain_topo')
    else:
        print('[OK] h1 -> h2 ping succeeded (three_chain)')

    return net, h1, h2, rn1, rn2, r_mb1, rn3, r_mb2, rn4, r_mb3, rn5
