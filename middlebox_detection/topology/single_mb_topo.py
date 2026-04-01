"""
Single-MB topology: 5 hops
h1 --10Mbps-- rn1 --10Mbps-- rn2 --10Mbps-- r_mb --2Mbps-- rn3 --10Mbps-- h2
"""
from mininet.net import Mininet
from mininet.node import Node
from mininet.link import TCLink


class LinuxRouter(Node):
    def config(self, mac=None, ip=None, defaultRoute=None, lo='up', **params):
        r = super().config(mac=mac, ip=ip, defaultRoute=defaultRoute, lo=lo, **params)
        self.cmd('sysctl -w net.ipv4.ip_forward=1')
        return r

    def terminate(self):
        self.cmd('sysctl -w net.ipv4.ip_forward=0')
        super().terminate()


def create_single_mb_topo():
    net = Mininet(controller=None, link=TCLink)

    h1  = net.addHost('h1',  ip='10.0.1.1/24', defaultRoute='via 10.0.1.2')
    rn1 = net.addHost('rn1', ip='10.0.1.2/24', cls=LinuxRouter)
    rn2 = net.addHost('rn2', ip='10.0.2.2/24', cls=LinuxRouter)
    r_mb= net.addHost('r_mb',ip='10.0.3.2/24', cls=LinuxRouter)
    rn3 = net.addHost('rn3', ip='10.0.4.2/24', cls=LinuxRouter)
    h2  = net.addHost('h2',  ip='10.0.5.2/24', defaultRoute='via 10.0.5.1')

    net.addLink(h1,   rn1,  intfName1='h1-eth0',    intfName2='rn1-eth0',
                bw=10, max_queue_size=100)
    net.addLink(rn1,  rn2,  intfName1='rn1-eth1',   intfName2='rn2-eth0',
                bw=10, max_queue_size=100)
    net.addLink(rn2,  r_mb, intfName1='rn2-eth1',   intfName2='r_mb-eth0',
                bw=10, max_queue_size=100)
    net.addLink(r_mb, rn3,  intfName1='r_mb-eth1',  intfName2='rn3-eth0',
                bw=2,  max_queue_size=10)
    net.addLink(rn3,  h2,   intfName1='rn3-eth1',   intfName2='h2-eth0',
                bw=10, max_queue_size=100)

    net.start()

    # Set MTU 1500 on all interfaces
    for node in [h1, rn1, rn2, r_mb, rn3, h2]:
        for intf in node.intfList():
            if intf.name != 'lo':
                node.cmd(f'ip link set {intf.name} mtu 1500')

    # Configure additional IPs on router interfaces
    rn1.cmd('ip addr add 10.0.2.1/24 dev rn1-eth1')
    rn2.cmd('ip addr add 10.0.3.1/24 dev rn2-eth1')
    r_mb.cmd('ip addr add 10.0.4.1/24 dev r_mb-eth1')
    rn3.cmd('ip addr add 10.0.5.1/24 dev rn3-eth1')

    # Static routes
    h1.cmd('ip route add default via 10.0.1.2')

    rn1.cmd('ip route add 10.0.3.0/24 via 10.0.2.2')
    rn1.cmd('ip route add 10.0.4.0/24 via 10.0.2.2')
    rn1.cmd('ip route add 10.0.5.0/24 via 10.0.2.2')

    rn2.cmd('ip addr add 10.0.2.2/24 dev rn2-eth0')
    rn2.cmd('ip route add 10.0.1.0/24 via 10.0.2.1')
    rn2.cmd('ip route add 10.0.4.0/24 via 10.0.3.2')
    rn2.cmd('ip route add 10.0.5.0/24 via 10.0.3.2')

    r_mb.cmd('ip addr add 10.0.3.2/24 dev r_mb-eth0')
    r_mb.cmd('ip route add 10.0.1.0/24 via 10.0.3.1')
    r_mb.cmd('ip route add 10.0.2.0/24 via 10.0.3.1')
    r_mb.cmd('ip route add 10.0.5.0/24 via 10.0.4.2')

    rn3.cmd('ip addr add 10.0.4.2/24 dev rn3-eth0')
    rn3.cmd('ip route add 10.0.1.0/24 via 10.0.4.1')
    rn3.cmd('ip route add 10.0.2.0/24 via 10.0.4.1')
    rn3.cmd('ip route add 10.0.3.0/24 via 10.0.4.1')

    h2.cmd('ip route add default via 10.0.5.1')

    # Verify connectivity
    result = h1.cmd('ping -c 3 -W 2 10.0.5.2') or ''
    if '1 received' not in result and '2 received' not in result and '3 received' not in result:
        print('[WARN] h1 -> h2 ping failed, check routing')
    else:
        print('[OK] h1 -> h2 ping succeeded')

    return net, h1, h2, rn1, rn2, r_mb, rn3


if __name__ == '__main__':
    import os, sys
    from mininet.log import setLogLevel
    from mininet.cli import CLI

    if os.geteuid() != 0:
        print('ERROR: Must run with sudo'); sys.exit(1)

    setLogLevel('info')
    net, h1, h2, rn1, rn2, r_mb, rn3 = create_single_mb_topo()

    try:
        print('\n--- h1 routes ---')
        print(h1.cmd('ip route'))
        print('--- r_mb routes ---')
        print(r_mb.cmd('ip route'))
        print('--- h1 -> h2 ping ---')
        print(h1.cmd('ping -c 3 10.0.5.2'))
        CLI(net)
    finally:
        net.stop()
        os.system('mn -c > /dev/null 2>&1')
