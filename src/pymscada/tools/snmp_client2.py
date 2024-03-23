import asyncio
from pysnmp.hlapi.asyncio import *


async def run():
    base = [
        '1.3.6.1.2.1.2.2.1.2.',  # name
        # '.1.3.6.1.2.1.2.2.1.4.',  # mtu
        # '.1.3.6.1.2.1.2.2.1.6.',  # mac address
        # '.1.3.6.1.2.1.2.2.1.7.',  # admin status
        # '.1.3.6.1.2.1.2.2.1.8.',  # oper status
        '1.3.6.1.2.1.31.1.1.1.6.',  # bytes in
        # '.1.3.6.1.2.1.31.1.1.1.7.',  # packets in
        # '.1.3.6.1.2.1.2.2.1.13.',  # discards in
        # '.1.3.6.1.2.1.2.2.1.14.',  # errors in
        '1.3.6.1.2.1.31.1.1.1.10.',  # bytes out
        # '.1.3.6.1.2.1.31.1.1.1.11.',  # packets out
        # '.1.3.6.1.2.1.2.2.1.19.',  # discards out
        # '.1.3.6.1.2.1.2.2.1.20.',  # errors out
    ]
    oids = []
    for i in range(1, 9):
        for b in base:
            oids.append(ObjectType(ObjectIdentity(f'{b}{i}')))
    ip_address = '172.26.3.254'
    community = 'public'

    snmp_engine = SnmpEngine()

    r = await getCmd(
        snmp_engine,
        CommunityData(community),
        UdpTransportTarget((ip_address, 161)),
        ContextData(),
        *oids
    )
    errorIndication, errorStatus, errorIndex, varBinds = r
    if errorIndication:
        print(errorIndication)
    elif errorStatus:
        print('%s at %s' % (
            errorStatus.prettyPrint(),
            errorIndex and varBinds[int(errorIndex) - 1][0] or '?'))
    else:
        for varBind in varBinds:
            oid, value = varBind
            print(str(oid), type(oid), str(value), type(value))
    # snmp_engine.transportDispatcher.closeDispatcher()


if __name__ == '__main__':
    """Starts with creating an event loop."""
    asyncio.run(run())
