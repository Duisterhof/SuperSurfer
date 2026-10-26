"""Installed fabric policy rejects Ethernet and alias override fallback."""
import json
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from aml.ssh_budget import validate_network_policy

class FabricPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'policy.json'
        self.path.write_text(json.dumps(dict(aliases={'cluster-1':'172.16.1.10'},alias_prefix='cluster-',
            required_cidr='172.16.1.0/24',blocked_cidrs=['10.1.1.0/24'])))
    def check(self,target,hostname=None,options=None):
        validate_network_policy(options or [],target,dict(hostname=hostname) if hostname else None,self.path)
    def test_valid_compute_route_and_gateway_control_remain_available(self):
        self.check('user@cluster-1','172.16.1.10')
        self.check('gateway','128.2.1.1')
        self.check('gateway',options=['-W','172.16.1.10:22'])
    def test_literal_ethernet_and_hostname_overrides_fail_closed(self):
        for target,hostname in [('10.1.1.10',None),('cluster-1','10.1.1.10'),('cluster-1','172.16.1.11'),('cluster-unknown','cluster-unknown')]:
            with self.subTest(target=target,hostname=hostname),self.assertRaises(RuntimeError):self.check(target,hostname)
    def test_forwarding_ethernet_or_alias_dns_fallback_is_rejected(self):
        for address in ['10.1.1.10:22','cluster-1:22','cluster-unknown:22']:
            with self.assertRaises(RuntimeError):self.check('gateway',options=['-W',address])
    def test_accounts_without_policy_keep_existing_behavior(self):
        self.path.unlink();self.check('cluster-1','10.1.1.10')
