import os, sys, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import noip, sg


class NoipTest(unittest.TestCase):
    def test_read_cred(self):
        with tempfile.NamedTemporaryFile('w', suffix='.sh', delete=False) as f:
            f.write('#!/bin/bash\nusername="a@b.c"\nexport password=p w$1\nother=1\n')
        self.assertEqual(noip.read_cred(f.name), ('a@b.c', 'p w$1'))
        os.unlink(f.name)

    def test_exit_code(self):
        with tempfile.NamedTemporaryFile('w', delete=False) as f:
            f.write('username=u\npassword=p\n')
        for res, code in [('good 1.2.3.4', 0), ('nochg 1.2.3.4', 0), ('nohost', 1), ('badauth', 1)]:
            with mock.patch.object(noip, 'update', return_value=res) as up:
                self.assertEqual(noip.main(['x.ddns.net', '--cred', f.name, '--ip', '1.1.1.1']), code)
                up.assert_called_once_with('x.ddns.net', 'u', 'p', ip='1.1.1.1')
        os.unlink(f.name)


    def test_tls_context(self):
        import ssl
        ctx = noip.tls_context()
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)       # 仍驗證憑證
        self.assertTrue(ctx.check_hostname)                        # 仍驗證主機名稱
        self.assertFalse(ctx.verify_flags & ssl.VERIFY_X509_STRICT)


class SgTest(unittest.TestCase):
    def test_plan(self):
        want = {'a': {'1.1.1.1/32'}, 'b': {'2.2.2.2/32', '3.3.3.3/32'}, 'c': set(), 'd': {'4.4.4.4/32'}}
        have = {'a': {'9.9.9.9/32'}, 'b': {'2.2.2.2/32'}, 'c': {'8.8.8.8/32'}, 'd': {'4.4.4.4/32'}, 'other': {'7.7.7.7/32'}}
        add, rev = sg.plan(want, have)
        self.assertEqual(add, [('a', '1.1.1.1/32'), ('b', '3.3.3.3/32')])
        self.assertEqual(rev, [('a', '9.9.9.9/32')])    # c 解析不到不動；other 不在監看清單不動

    def test_run_once_order_and_dry(self):
        conf = {'group_id': 'sg-1', 'port': 22, 'watch': {'a': 'a.ddns.net'}}
        calls = []
        def fake_aws(*args):
            calls.append(args[0])
            if args[0] == 'describe-security-groups':
                return {'SecurityGroups': [{'IpPermissions': [{'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22,
                        'IpRanges': [{'CidrIp': '9.9.9.9/32', 'Description': 'a'}]}]}]}
            return {}
        with mock.patch.object(sg, 'aws', fake_aws), mock.patch.object(sg, 'resolve', return_value=['1.1.1.1']):
            sg.run_once(conf)
            self.assertEqual(calls, ['describe-security-groups', 'authorize-security-group-ingress', 'revoke-security-group-ingress'])
            calls.clear()
            sg.run_once(conf, dry=True)
            self.assertEqual(calls, ['describe-security-groups'])

    def test_perm(self):
        self.assertEqual(sg.perm('1.1.1.1/32', 22, 'a'), 'IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=1.1.1.1/32,Description=a}]')
        self.assertEqual(sg.perm('1.1.1.1/32', 22), 'IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=1.1.1.1/32}]')


if __name__ == '__main__':
    unittest.main()
