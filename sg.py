#!/usr/bin/python3
# -*- coding: utf-8 -*-
import os, json, subprocess
from time import sleep
from datetime import datetime

def dig(domain):
    return subprocess.check_output(['dig', '+short', domain]).decode('utf8').strip().split('\n')

def aws_ec2(cmd):
    # type(cmd) = list
    try:
        return json.loads(subprocess.check_output(['aws', 'ec2']+cmd))
    except:
        return None

def sg(gid=None):
    gid = gid if gid else SG_ID
    return aws_ec2(['describe-security-groups', '--group-ids', gid])['SecurityGroups'][0]['IpPermissions']

def old_cidr(description):
    a = [i for i in sg() if 'FromPort' in i and i['FromPort'] == 22 and 'ToPort' in i and i['ToPort'] == 22][0]['IpRanges']
    a = [i for i in a if i['Description'] == description]
    if len(a) == 1:
        return a[0]['CidrIp']

def sg_auth(cidr=None, gid=None, protocol='tcp', port=22, description='nas'):
    gid = gid if gid else SG_ID
    if not cidr:
        ip = dig('0.noip.me')
        if len(ip) == 1:
            cidr = '%s/32'%ip[0]
    aws_ec2(['authorize-security-group-ingress', '--group-id', gid, '--ip-permissions', "IpProtocol=%s,FromPort=%d,ToPort=%d,IpRanges=[{CidrIp=%s,Description=%s}]"%(protocol, port, port, cidr, description)])

def sg_revoke(cidr=None, gid=None, protocol='tcp', port=22, description='nas'):
    gid = gid if gid else SG_ID
    if not cidr:
        cidr = [j['CidrIp'] for i in sg(gid) for j in i['IpRanges'] if 'Description' in j and j['Description']==description][0]
    aws_ec2(['revoke-security-group-ingress', '--group-id', gid, '--protocol', protocol, '--port', str(port), '--cidr', cidr])

def main(d):
    for name in d:
        ips = dig(d[name])
        print(name, *ips)
        if not os.path.isfile(d[name]) or not all(i in ips for i in open(d[name]).read().split('\n')):
            if os.path.isfile(d[name]):
                sg_revoke(old_cidr(name), description=name)
                print('revoke', name)
            new_cidr = ','.join([ip+'/32' for ip in ips])
            sg_auth(new_cidr, description=name)
            print('auth', name)
            open(d[name], 'w').write('\n'.join(ips))

SG_ID, d = json.load(open('arg.json'))
# arg.json
# ["sg-0123456789_aws_security_group_id", {"short_name1": "noip_domain1.noip.com", "short_name2": "noip_domain2.noip.com"}]

if __name__ == '__main__':
    while not os.path.isfile('break'):
        print(datetime.utcnow().isoformat())
        main(d)
        sleep(300)
