from os.path import dirname, join
from types import SimpleNamespace
from unittest import TestCase

from requests import HTTPError
from requests_mock import mock as requests_mock

from octodns.provider import ProviderException
from octodns.provider.yaml import YamlProvider
from octodns.record import Create, Delete, Record, Update
from octodns.zone import Zone

from octodns_mythicbeasts import (
    MythicBeastsProvider,
    MythicBeastsZoneNotFoundException,
    _normalise_content,
    _normalise_record_name,
    _normalise_zone_name,
)


class TestMythicBeastsProvider(TestCase):
    expected = Zone('unit.tests.', [])
    source = YamlProvider(
        'test_expected',
        join(dirname(__file__), 'config'),
        escaped_semicolons=False,
    )
    source.populate(expected)

    # Dump anything we don't support from expected
    for record in list(expected.records):
        if record._type not in MythicBeastsProvider.SUPPORTS:
            expected.remove_record(record)

    @property
    def auth_url(self):
        return f'{MythicBeastsProvider.MB_API_AUTH_URL}login'

    @property
    def zones_url(self):
        return f'{MythicBeastsProvider.MB_API_BASE_URL}zones'

    @property
    def records_url(self):
        return f'{MythicBeastsProvider.MB_API_BASE_URL}zones/unit.tests/records'

    def _provider(self):
        return MythicBeastsProvider('test', 'api-key', 'api-secret')

    def _api_records_for_zone(self, provider, zone):
        records = []
        for record in sorted(zone.records, key=lambda r: (r.name, r._type)):
            _, content = provider._gen_data(record)
            records.extend(content['records'])
        return records

    def test_normalise_helpers(self):
        self.assertEqual('unit.tests.', _normalise_zone_name('unit.tests'))
        self.assertEqual('unit.tests.', _normalise_zone_name('unit.tests.'))
        self.assertEqual('', _normalise_record_name('@'))
        self.assertEqual('www', _normalise_record_name('www'))

    def test_normalise_content(self):
        zone = Zone('unit.tests.', [])
        alias = Record.new(
            zone,
            '',
            {'ttl': 300, 'type': 'ALIAS', 'value': 'target.unit.tests.'},
        )
        name, host, record_type = _normalise_content(alias)
        self.assertEqual('unit.tests', name)
        self.assertEqual('@', host)
        self.assertEqual('ANAME', record_type)

    def test_data_generation_helpers(self):
        with requests_mock() as mock:
            mock.post(
                self.auth_url, status_code=200, json={'access_token': 'token'}
            )
            provider = self._provider()

            records = [
                {'ttl': 300, 'data': '1.2.3.4'},
                {'ttl': 300, 'data': '5.6.7.8'},
            ]
            self.assertEqual(
                {'ttl': 300, 'type': 'A', 'values': ['1.2.3.4', '5.6.7.8']},
                provider._data_for_multiple('A', records),
            )
            self.assertEqual(
                {'ttl': 300, 'type': 'AAAA', 'value': '1::1'},
                provider._data_for_single(
                    'AAAA', [{'ttl': 300, 'data': '1::1'}]
                ),
            )
            self.assertEqual(
                {
                    'ttl': 300,
                    'type': 'MX',
                    'values': [
                        {'exchange': 'mx.unit.tests.', 'preference': 10}
                    ],
                },
                provider._data_for_MX(
                    'MX',
                    [{'ttl': 300, 'data': 'mx.unit.tests.', 'mx_priority': 10}],
                ),
            )
            self.assertEqual(
                {
                    'ttl': 600,
                    'type': 'SRV',
                    'values': [
                        {
                            'target': 'srv.unit.tests.',
                            'priority': 1,
                            'weight': 2,
                            'port': 3,
                        }
                    ],
                },
                provider._data_for_SRV(
                    'SRV',
                    [
                        {
                            'ttl': 600,
                            'data': 'srv.unit.tests.',
                            'srv_priority': 1,
                            'srv_weight': 2,
                            'srv_port': 3,
                        }
                    ],
                ),
            )
            self.assertEqual(
                {
                    'ttl': 3600,
                    'type': 'SSHFP',
                    'values': [
                        {
                            'fingerprint': 'abc',
                            'algorithm': 1,
                            'fingerprint_type': 2,
                        }
                    ],
                },
                provider._data_for_SSHFP(
                    'SSHFP',
                    [
                        {
                            'ttl': 3600,
                            'data': 'abc',
                            'sshfp_algorithm': 1,
                            'sshfp_type': 2,
                        }
                    ],
                ),
            )
            self.assertEqual(
                {
                    'ttl': 600,
                    'type': 'TLSA',
                    'values': [
                        {
                            'certificate_usage': 3,
                            'selector': 1,
                            'matching_type': 1,
                            'certificate_association_data': 'deadbeef',
                        }
                    ],
                },
                provider._data_for_TLSA(
                    'TLSA',
                    [
                        {
                            'ttl': 600,
                            'data': 'deadbeef',
                            'tlsa_usage': 3,
                            'tlsa_selector': 1,
                            'tlsa_matching': 1,
                        }
                    ],
                ),
            )
            self.assertEqual(
                {
                    'ttl': 300,
                    'type': 'CAA',
                    'values': [
                        {'flags': 0, 'tag': 'issue', 'value': 'ca.example'}
                    ],
                },
                provider._data_for_CAA(
                    'CAA',
                    [
                        {
                            'ttl': 300,
                            'data': 'ca.example',
                            'caa_flags': 0,
                            'caa_tag': 'issue',
                        }
                    ],
                ),
            )

    def test_init_login_failure_raises_provider_exception(self):
        with requests_mock() as mock:
            mock.post(self.auth_url, status_code=401, json={'detail': 'nope'})
            provider = self._provider()
            with self.assertRaises(ProviderException):
                _ = provider.zones

    def test_init_accepts_timeout_kwarg(self):
        with requests_mock() as mock:
            mock.post(
                self.auth_url, status_code=200, json={'access_token': 'token'}
            )

            provider = MythicBeastsProvider(
                'test', 'api-key', 'api-secret', timeout=5
            )

            self.assertEqual(5, provider._timeout)

    def test_zones_are_cached_and_normalised(self):
        with requests_mock() as mock:
            mock.post(
                self.auth_url, status_code=200, json={'access_token': 'token'}
            )
            mock.get(
                self.zones_url,
                status_code=200,
                json={'zones': ['unit.tests', 'example.com.']},
            )

            provider = self._provider()
            self.assertNotIn('Authorization', provider._sess.headers)

            first = provider.zones
            self.assertEqual(
                'Bearer token', provider._sess.headers['Authorization']
            )
            second = provider.zones
            self.assertIs(first, second)
            self.assertIn('unit.tests.', first)
            self.assertIn('example.com.', first)

            zone_gets = [
                req
                for req in mock.request_history
                if req.method == 'GET' and req.url == self.zones_url
            ]
            self.assertEqual(1, len(zone_gets))

            auth_posts = [
                req
                for req in mock.request_history
                if req.method == 'POST' and req.url == self.auth_url
            ]
            self.assertEqual(1, len(auth_posts))

    def test_zone_records_returns_empty_for_unknown_zone(self):
        with requests_mock() as mock:
            mock.post(
                self.auth_url, status_code=200, json={'access_token': 'token'}
            )
            mock.get(
                self.zones_url, status_code=200, json={'zones': ['example.com']}
            )

            provider = self._provider()
            records = provider.zone_records(Zone('unit.tests.', []))
            self.assertEqual([], records)

    def test_zone_records_uses_cache_after_first_fetch(self):
        with requests_mock() as mock:
            mock.post(
                self.auth_url, status_code=200, json={'access_token': 'token'}
            )
            mock.get(
                self.zones_url, status_code=200, json={'zones': ['unit.tests']}
            )
            mock.get(
                self.records_url,
                status_code=200,
                json={
                    'records': [
                        {'host': '@', 'type': 'A', 'ttl': 60, 'data': '1.2.3.4'}
                    ]
                },
            )

            provider = self._provider()
            zone = Zone('unit.tests.', [])

            first = provider.zone_records(zone)
            second = provider.zone_records(zone)
            self.assertIs(first, second)

            record_gets = [
                req
                for req in mock.request_history
                if req.method == 'GET' and req.url.startswith(self.records_url)
            ]
            self.assertEqual(1, len(record_gets))

    def test_populate_with_no_records_returns_true_when_zone_exists(self):
        with requests_mock() as mock:
            mock.post(
                self.auth_url, status_code=200, json={'access_token': 'token'}
            )
            mock.get(
                self.zones_url, status_code=200, json={'zones': ['unit.tests']}
            )
            mock.get(self.records_url, status_code=200, json={'records': []})

            provider = self._provider()
            zone = Zone('unit.tests.', [])
            self.assertTrue(provider.populate(zone))
            self.assertEqual(0, len(zone.records))

    def test_populate_returns_false_when_zone_does_not_exist(self):
        with requests_mock() as mock:
            mock.post(
                self.auth_url, status_code=200, json={'access_token': 'token'}
            )
            mock.get(self.zones_url, status_code=200, json={'zones': []})

            provider = self._provider()
            zone = Zone('unit.tests.', [])
            self.assertFalse(provider.populate(zone))
            self.assertEqual(0, len(zone.records))

    def test_populate_translates_aname_to_alias(self):
        with requests_mock() as mock:
            mock.post(
                self.auth_url, status_code=200, json={'access_token': 'token'}
            )
            mock.get(
                self.zones_url, status_code=200, json={'zones': ['unit.tests']}
            )
            mock.get(
                self.records_url,
                status_code=200,
                json={
                    'records': [
                        {
                            'host': '@',
                            'type': 'ANAME',
                            'ttl': 300,
                            'data': 'target.unit.tests.',
                        }
                    ]
                },
            )

            provider = self._provider()
            zone = Zone('unit.tests.', [])
            self.assertTrue(provider.populate(zone))

            alias = next(iter(zone.records))
            self.assertEqual('ALIAS', alias._type)
            self.assertEqual('target.unit.tests.', alias.value)

    def test_contents_for_tlsa(self):
        with requests_mock() as mock:
            mock.post(
                self.auth_url, status_code=200, json={'access_token': 'token'}
            )
            provider = self._provider()

            fake_record = SimpleNamespace(
                ttl=600,
                values=[
                    {
                        'certificate_usage': 3,
                        'selector': 1,
                        'matching_type': 1,
                        'certificate_association_data': 'deadbeef',
                    }
                ],
            )

            self.assertEqual(
                {
                    'records': [
                        {
                            'host': '_443._tcp',
                            'type': 'TLSA',
                            'ttl': 600,
                            'data': 'deadbeef',
                            'tlsa_usage': 3,
                            'tlsa_selector': 1,
                            'tlsa_matching': 1,
                        }
                    ]
                },
                provider._contents_for_TLSA(fake_record, '_443._tcp', 'TLSA'),
            )

    def test_txt_semicolon_escaping(self):
        with requests_mock() as mock:
            mock.post(
                self.auth_url, status_code=200, json={'access_token': 'token'}
            )
            provider = self._provider()

            # Reading: literal ';' from the API must be escaped for octoDNS.
            records = [
                {
                    'ttl': 300,
                    'data': 'v=spf1 include:_spf.example.com ~all; foo',
                }
            ]
            self.assertEqual(
                {
                    'ttl': 300,
                    'type': 'TXT',
                    'values': ['v=spf1 include:_spf.example.com ~all\\; foo'],
                },
                provider._data_for_TXT('TXT', records),
            )

            # Writing: octoDNS's escaped '\;' must be unescaped for the API.
            fake_record = SimpleNamespace(
                ttl=300, values=['v=spf1 include:_spf.example.com ~all\\; foo']
            )
            self.assertEqual(
                {
                    'records': [
                        {
                            'host': 'spf',
                            'type': 'TXT',
                            'ttl': 300,
                            'data': 'v=spf1 include:_spf.example.com ~all; foo',
                        }
                    ]
                },
                provider._contents_for_TXT(fake_record, 'spf', 'TXT'),
            )

    def test_populate_with_txt_semicolon_from_api(self):
        with requests_mock() as mock:
            mock.post(
                self.auth_url, status_code=200, json={'access_token': 'token'}
            )
            mock.get(
                self.zones_url, status_code=200, json={'zones': ['unit.tests']}
            )
            mock.get(
                self.records_url,
                status_code=200,
                json={
                    'records': [
                        {
                            'host': 'spf',
                            'type': 'TXT',
                            'ttl': 300,
                            'data': 'v=spf1 include:_spf.example.com ~all; foo',
                        }
                    ]
                },
            )

            provider = self._provider()
            zone = Zone('unit.tests.', [])
            # lenient defaults to False, so this raises if unescaped
            self.assertTrue(provider.populate(zone))

            record = next(iter(zone.records))
            self.assertEqual(
                ['v=spf1 include:_spf.example.com ~all\\; foo'], record.values
            )

    def test_populate_from_json_records(self):
        with requests_mock() as mock:
            mock.post(
                self.auth_url, status_code=200, json={'access_token': 'token'}
            )
            mock.get(
                self.zones_url, status_code=200, json={'zones': ['unit.tests']}
            )

            provider = self._provider()

            api_records = self._api_records_for_zone(provider, self.expected)
            # Ensure filtering code paths are also covered.
            api_records.append(
                {'host': '@', 'type': 'SOA', 'ttl': 300, 'data': 'ignored'}
            )
            api_records.append(
                {'host': '@', 'type': 'PTR', 'ttl': 300, 'data': 'ignored'}
            )

            mock.get(
                self.records_url, status_code=200, json={'records': api_records}
            )

            zone = Zone('unit.tests.', [])
            self.assertTrue(provider.populate(zone))
            self.assertEqual(len(self.expected.records), len(zone.records))

            changes = self.expected.changes(zone, provider)
            self.assertEqual([], changes)

    def test_apply_create_update_delete(self):
        with requests_mock() as mock:
            mock.post(
                self.auth_url, status_code=200, json={'access_token': 'token'}
            )
            mock.get(
                self.zones_url, status_code=200, json={'zones': ['unit.tests']}
            )

            provider = self._provider()

            existing = Zone('unit.tests.', [])
            existing.add_record(
                Record.new(
                    existing,
                    'edit',
                    {'ttl': 300, 'type': 'TXT', 'value': 'old'},
                )
            )
            existing.add_record(
                Record.new(
                    existing,
                    'gone',
                    {'ttl': 300, 'type': 'TXT', 'value': 'delete-me'},
                )
            )

            mock.get(
                self.records_url,
                status_code=200,
                json={
                    'records': self._api_records_for_zone(provider, existing)
                },
            )

            wanted = Zone('unit.tests.', [])
            wanted.add_record(
                Record.new(
                    wanted, 'edit', {'ttl': 300, 'type': 'TXT', 'value': 'new'}
                )
            )
            wanted.add_record(
                Record.new(
                    wanted,
                    'fresh',
                    {'ttl': 60, 'type': 'A', 'values': ['1.2.3.4', '5.6.7.8']},
                )
            )

            mock.put(
                f'{MythicBeastsProvider.MB_API_BASE_URL}zones/unit.tests/records/edit/TXT',
                status_code=200,
                json={'ok': True},
            )
            mock.delete(
                f'{MythicBeastsProvider.MB_API_BASE_URL}zones/unit.tests/records/gone/TXT',
                status_code=200,
                json={'ok': True},
            )
            mock.post(
                f'{MythicBeastsProvider.MB_API_BASE_URL}zones/unit.tests/records/fresh/A',
                status_code=200,
                json={'ok': True},
            )

            plan = provider.plan(wanted)
            self.assertEqual(
                1, len([c for c in plan.changes if isinstance(c, Update)])
            )
            self.assertEqual(
                1, len([c for c in plan.changes if isinstance(c, Delete)])
            )
            self.assertEqual(
                1, len([c for c in plan.changes if isinstance(c, Create)])
            )
            self.assertIn('unit.tests.', provider._zone_records)

            self.assertEqual(3, provider.apply(plan))
            self.assertNotIn('unit.tests.', provider._zone_records)

            update_requests = [
                req
                for req in mock.request_history
                if req.method == 'PUT'
                and req.url.endswith('/zones/unit.tests/records/edit/TXT')
            ]
            self.assertEqual(1, len(update_requests))
            self.assertEqual(
                {
                    'records': [
                        {
                            'host': 'edit',
                            'type': 'TXT',
                            'ttl': 300,
                            'data': 'new',
                        }
                    ]
                },
                update_requests[0].json(),
            )

            delete_requests = [
                req
                for req in mock.request_history
                if req.method == 'DELETE'
                and req.url.startswith(
                    f'{MythicBeastsProvider.MB_API_BASE_URL}zones/unit.tests/records/gone/TXT'
                )
            ]
            self.assertEqual(1, len(delete_requests))
            self.assertEqual(
                {'exclude-generated': ['true']}, delete_requests[0].qs
            )

            create_requests = [
                req
                for req in mock.request_history
                if req.method == 'POST'
                and req.url.endswith('/zones/unit.tests/records/fresh/A')
            ]
            self.assertEqual(1, len(create_requests))
            self.assertEqual(
                {
                    'records': [
                        {
                            'host': 'fresh',
                            'type': 'A',
                            'ttl': 60,
                            'data': '1.2.3.4',
                        },
                        {
                            'host': 'fresh',
                            'type': 'A',
                            'ttl': 60,
                            'data': '5.6.7.8',
                        },
                    ]
                },
                create_requests[0].json(),
            )

    def test_apply_missing_zone_raises(self):
        with requests_mock() as mock:
            mock.post(
                self.auth_url, status_code=200, json={'access_token': 'token'}
            )
            mock.get(self.zones_url, status_code=200, json={'zones': []})
            provider = self._provider()

            wanted = Zone('unit.tests.', [])
            wanted.add_record(
                Record.new(
                    wanted, 'txt', {'ttl': 300, 'type': 'TXT', 'value': 'value'}
                )
            )
            plan = SimpleNamespace(desired=wanted, changes=[])

            with self.assertRaisesRegex(
                MythicBeastsZoneNotFoundException,
                r'^zone unit\.tests\. does not exist in Mythic Beasts account',
            ):
                provider._apply(plan)

    def test_request_non_2xx_raises_http_error(self):
        with requests_mock() as mock:
            mock.post(
                self.auth_url, status_code=200, json={'access_token': 'token'}
            )
            mock.get(self.zones_url, status_code=500, json={'error': 'boom'})

            provider = self._provider()
            with self.assertRaises(HTTPError):
                _ = provider.zones

    def test_request_helper_passes_expected_kwargs(self):
        with requests_mock() as mock:
            mock.post(
                self.auth_url, status_code=200, json={'access_token': 'token'}
            )
            mock.patch(
                f'{MythicBeastsProvider.MB_API_BASE_URL}zones/unit.tests/records/example/TXT',
                status_code=200,
                json={'ok': True},
            )

            provider = self._provider()
            provider._patch(
                'zones/unit.tests/records/example/TXT',
                params={'a': 'b'},
                json={'records': []},
            )

            patch_requests = [
                req for req in mock.request_history if req.method == 'PATCH'
            ]
            self.assertEqual(1, len(patch_requests))
            self.assertEqual({'a': ['b']}, patch_requests[0].qs)
