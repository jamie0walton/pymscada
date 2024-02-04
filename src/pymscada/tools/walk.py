"""
Walk whole MIB
++++++++++++++

Send a series of SNMP GETNEXT requests using the following options:

* with SNMPv3, user 'usr-md5-none', MD5 authentication, no privacy
* over IPv4/UDP
* to an Agent at demo.snmplabs.com:161
* for all OIDs in IF-MIB

Functionally similar to:

| $ snmpwalk -v3 -lauthPriv -u usr-md5-none -A authkey1 -X privkey1 demo.snmplabs.com  IF-MIB::

"""#
from pysnmp.hlapi import *

mibs = {
    'MIKROTIK-MIB': '1.3.6.1.4.1.14988',
    'MIB-2': '1.3.6.1.2.1',
    'HOST-RESOURCES-MIB': '1.3.6.1.2.1.25',
    'IF-MIB': '1.3.6.1.2.1.2',
    'IP-MIB': '1.3.6.1.2.1.4',
    'IP-FORWARD-MIB': '1.3.6.1.2.1.4.21',
    'IPV6-MIB': '1.3.6.1.2.1.55',
    'BRIDGE-MIB': '1.3.6.1.2.1.17',
    'DHCP-SERVER-MIB': '1.3.6.1.4.1.14988.1.1.8',
    'CISCO-AAA-SESSION-MIB': '1.3.6.1.4.1.9.9.39',
    'ENTITY-MIB': '1.3.6.1.2.1.47',
    'UPS-MIB': '1.3.6.1.2.1.33',
    'SQUID-MIB': '1.3.6.1.4.1.3495',
}

iterator = nextCmd(
    SnmpEngine(),
    UsmUserData('public'),
    UdpTransportTarget(('172.26.3.254', 161)),
    ContextData(),
    # ObjectType(ObjectIdentity('1.3.6.1.2.1.1.1.0')),
    # ObjectType(ObjectIdentity('1.3.6.1.2.1.1.6.0'))
    ObjectType(ObjectIdentity(mibs['MIB-2']))
)

for errorIndication, errorStatus, errorIndex, varBinds in iterator:
    if errorIndication:
        print(errorIndication)
        break
    elif errorStatus:
        print('%s at %s' % (errorStatus.prettyPrint(),
                            errorIndex and varBinds[int(errorIndex) - 1][0] or '?'))
        break
    else:
        for varBind in varBinds:
            print(' = '.join([x.prettyPrint() for x in varBind]))
