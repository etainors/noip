# -*- coding: utf-8 -*-
#
# 定時執行
# add /etc/crontab
# 0,10,20,30,40,50	*	*	*	*	admin	/var/services/homes/admin/noip.sh
# restart Synology NAS
#
# 開機執行
# edit: /etc/init.d/noip.sh
# add 8 lines:
#! /bin/sh
### BEGIN INIT INFO
# Provides:       noip
# Required-Start: $all
# Required-Stop:
# Default-Start:  2 3 4 5
# Default-Stop:   0 1 6
### END INIT INFO
#
# add: /usr/bin/python /home/ubuntu/noip.py
# $ sudo chmod 755 /etc/init.d/noip.sh
# $ sudo update-rc.d noip.sh defaults
# remove:
# $ sudo update-rc.d noip.sh remove
import requests
from bs4 import BeautifulSoup
from datetime import datetime
bs = lambda i:BeautifulSoup(i, 'html.parser')

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36'

def log(s):
    t = datetime.utcnow().isoformat()
    print t, s
    open('log.txt', 'a').write(t+'\t'+s+'\n')

# 使用noip的API
def dynupdate(username, password, hostname, ip=''):
    url = 'https://'+username+':'+password+'@dynupdate.no-ip.com/nic/update?hostname='+hostname+('&myip='+ip if ip else '')
    log(requests.get(url).content.strip())

def login(username, password):
    s = requests.Session()
    
    # 讀登入頁取token
    log('read login')
    web1 = s.get('https://www.noip.com/login', headers={'User-Agent':UA})
    soup1 = bs(web1.content)
    
    # 登入
    log('login')
    s.post('https://www.noip.com/login', data={
        'username':username,
        'password':password,
        'submit_login_page':'1',
        '_token':soup1.find('input', {'name':'_token'})['value'],
        'Login':''
    })
    
    return s

# 使用網頁，改host_to的ip為host_from的ip
def main_v1(username, password, host_from, host_to):
    s = login(username, password)
    
    # 讀管理頁
    log('read manage')
    web2 = s.get('https://www.noip.com/members/dns/')
    soup2 = bs(web2.content)
    if len(set(map(lambda i:i.text.strip(), soup2.select('td.withright')))) == 1:
        log('no need modify, logout')
        s.get('https://www.noip.com/logout')
        exit()
    
    new_ip = ''
    mod_url = []
    for i in soup2.select('tr.service-entry'):
        if i.find('td', {'class':'entry'}).text.strip() == host_from:
            new_ip = i.find('td', {'class':'withright'}).text.strip()
        if i.find('td', {'class':'entry'}).text.strip() in host_to:
            mod_url.append('https://www.noip.com/members/dns/'+i.find('a', {'class':'bullet-modify'})['href'])
    
    # 偵錯
    if not new_ip or len(mod_url) != len(host_to):
        log('host_from/host_to setting error')
        s.get('https://www.noip.com/logout')
        exit()

    # 更新IP
    for url in mod_url:
        log('read modity')
        web3 = s.get(url)
        soup3 = bs(web3.content)
        data3 = dict((i, soup3.find('input', {'name':i})['value']) for i in ['host[domain]', 'host[host]', 'host[port][ip]', 'host[port][port]', 'host[ttl]', 'nlocations', 'token'])
        data3.update({
            'do':'update',
            'host[group_id]':'0',
            'host[ip]':new_ip,
            'host[mx][0][priority]':'5',
            'host[redirect][protocol]':'http',
            'host[type]':'a',
        })
        log('modity ip to '+new_ip)
        s.post(url, data=data3)

    # 檢查結果
    log('read manage')
    web4 = s.get('https://www.noip.com/members/dns/')
    soup4 = bs(web4.content)
    if set(map(lambda i:i.text.strip(), soup4.select('td.withright'))) != set([new_ip]):
        log('update '+new_ip+' error')
        s.get('https://www.noip.com/logout')
        exit()

    # 登出
    log('logout')
    s.get('https://www.noip.com/logout')
    log('update to '+new_ip)

# 使用網頁，改host的ip
def main(username, password, host, ip):
    s = login(username, password)
    
    # 讀管理頁
    log('read manage')
    web2 = s.get('https://www.noip.com/members/dns/')
    soup2 = bs(web2.content)
    mod_url = []
    for i in soup2.select('tr.service-entry'):
        if i.find('td', {'class':'entry'}).text.strip() == host:
            if i.find('td', {'class':'withright'}).text.strip() == ip:
                log('no need modify, logout')
                s.get('https://www.noip.com/logout')
                exit()
            mod_url.append('https://www.noip.com/members/dns/'+i.find('a', {'class':'bullet-modify'})['href'])
    
    # 偵錯
    if not mod_url:
        log(host+' not in account: '+username)
        s.get('https://www.noip.com/logout')
        exit()
    
    # 更新IP
    for url in mod_url:
        log('read modity')
        web3 = s.get(url)
        soup3 = bs(web3.content)
        data3 = dict((i, soup3.find('input', {'name':i})['value']) for i in ['host[domain]', 'host[host]', 'host[port][ip]', 'host[port][port]', 'host[ttl]', 'nlocations', 'token'])
        data3.update({
            'do':'update',
            'host[group_id]':'0',
            'host[ip]':ip,
            'host[mx][0][priority]':'5',
            'host[redirect][protocol]':'http',
            'host[type]':'a',
        })
        log('modity')
        s.post(url, data=data3)
    
    # 檢查結果
    log('read manage')
    web4 = s.get('https://www.noip.com/members/dns/')
    soup4 = bs(web4.content)
    for i in soup4.select('tr.service-entry'):
        if i.find('td', {'class':'entry'}).text.strip() == host:
            if i.find('td', {'class':'withright'}).text.strip() != ip:
                log('update '+host+' to '+ip+' error')
                s.get('https://www.noip.com/logout')
                exit()
    
    # 登出
    log('logout')
    s.get('https://www.noip.com/logout')
    
    log(host+' update to '+ip)

if __name__ == '__main__':
    import argparse
    from sys import argv
    if len(argv) > 1 and argv[1] == 'dyn':
        parser = argparse.ArgumentParser()
        parser.add_argument('mod', help='dyn: use noip api')
        parser.add_argument('-u', '--username', default='', help='noip login username')
        parser.add_argument('-p', '--password', default='', help='noip login password')
        parser.add_argument('-d', '--domain', default='', help='noip domain to update')
        parser.add_argument('-i', '--ip', default='', help='noip ip to update to')
        args = parser.parse_args()
        dynupdate(args.username, args.password, args.domain, args.ip)
    elif len(argv) > 1 and argv[1] == 'h2h':
        parser = argparse.ArgumentParser()
        parser.add_argument('mod', help='h2h: use web, ip from host to hosts in same account')
        parser.add_argument('-u', '--username', default='', help='noip login username')
        parser.add_argument('-p', '--password', default='', help='noip login password')
        parser.add_argument('-f', '--host_from', default='', help='ip from the host')
        parser.add_argument('-t', '--host_to', default='', help='ip to the hosts, separate by comma')
        args = parser.parse_args()
        main_v1(args.username, args.password, args.host_from, args.host_to.split(','))
    elif len(argv) > 1 and argv[1] == 'i2h':
        parser = argparse.ArgumentParser()
        parser.add_argument('mod', help='i2h: use noip web interface')
        parser.add_argument('-u', '--username', default='', help='noip login username')
        parser.add_argument('-p', '--password', default='', help='noip login password')
        parser.add_argument('-d', '--domain', default='', help='noip domain to update')
        parser.add_argument('-i', '--ip', default='', help='noip ip to update to')
        args = parser.parse_args()
        main(args.username, args.password, args.domain, args.ip)
    else:
        parser = argparse.ArgumentParser()
        parser.add_argument('mod', help='you can use [dyn|h2h|i2h], dyn -h, h2h -h, i2h -h for more detail. And mod must be first argument.')
        args = parser.parse_args()

'''
exit()
python
from noip import *
'''
