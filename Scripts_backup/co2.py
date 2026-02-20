from pysnmp.entity.engine import SnmpEngine
from pysnmp.hlapi import *
from pysnmp.hlapi.asyncio import getCmd, CommunityData, UdpTransportTarget, ContextData
from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType


def get_snmp_data(ip, oid, community='public'):
    """Fetch SNMP data using SNMPv2c."""
    iterator = getCmd(
        SnmpEngine(),
        CommunityData(community, mpModel=1),  # SNMPv2c (mpModel=1)
        UdpTransportTarget((ip, 161), timeout=3, retries=2),
        ContextData(),
        ObjectType(ObjectIdentity(oid))
    )

    for (error_indication, error_status, error_index, var_binds) in iterator:
        if error_indication:
            print(f"[ERROR] SNMP Error for {ip}: {error_indication}")
        elif error_status:
            print(f"[ERROR] SNMP Error for {ip}: {error_status.prettyPrint()} at {error_index}")
        else:
            for var_bind in var_binds:
                print(f"[INFO] SNMP Response from {ip}: {var_bind.prettyPrint()}")

def main():
    """Run SNMPv2c requests for multiple devices."""
    ip_list = ['10.206.155.1', '10.206.155.6', '10.200.33.2', '10.206.163.65']
    oid = '1.3.6.1.4.1.9.9.618.1.8.4'

    # Deneme için farklı community string kullanabilirsin
    community_list = ["public", "private", "snmp_read"]

    for community in community_list:
        print(f"\n[INFO] Testing SNMPv2c with community: {community}")
        for ip in ip_list:
            get_snmp_data(ip, oid, community)

if __name__ == "__main__":
    main()
