#
#
#

from os.path import dirname, join
from unittest import TestCase

from requests_mock import ANY
from requests_mock import mock as requests_mock

from octodns.provider.yaml import YamlProvider
from octodns.record import Create, Delete, Record, Update
from octodns.zone import Zone

from octodns_mythicbeasts import (
    MythicBeastsProvider,
    add_trailing_dot,
    remove_trailing_dot,
)


class TestMythicBeastsProvider(TestCase):
    expected = Zone('unit.tests.', [])
    source = YamlProvider('test_expected', join(dirname(__file__), 'config'))
    source.populate(expected)

    # Dump anything we don't support from expected
    for record in list(expected.records):
        if record._type not in MythicBeastsProvider.SUPPORTS:
            expected.remove_record(record)

    def test_trailing_dot(self):
        with self.assertRaises(AssertionError) as err:
            add_trailing_dot('unit.tests.')
        self.assertEqual('Value already has trailing dot', str(err.exception))

        with self.assertRaises(AssertionError) as err:
            remove_trailing_dot('unit.tests')
        self.assertEqual(
            'Value already missing trailing dot', str(err.exception)
        )

        self.assertEqual(add_trailing_dot('unit.tests'), 'unit.tests.')
        self.assertEqual(remove_trailing_dot('unit.tests.'), 'unit.tests')

    def test_data_for_single(self):
        test_data = {
            'raw_values': [{'value': 'a:a::c', 'ttl': 0}],
            'zone': 'unit.tests.',
        }
        test_single = MythicBeastsProvider._data_for_single('', test_data)
        self.assertTrue(isinstance(test_single, dict))
        self.assertEqual('a:a::c', test_single['value'])

    def test_data_for_multiple(self):
        test_data = {
            'raw_values': [
                {'value': 'b:b::d', 'ttl': 60},
                {'value': 'a:a::c', 'ttl': 60},
            ],
            'zone': 'unit.tests.',
        }
        test_multiple = MythicBeastsProvider._data_for_multiple('', test_data)
        self.assertTrue(isinstance(test_multiple, dict))
        self.assertEqual(2, len(test_multiple['values']))

    def test_data_for_txt(self):
        test_data = {
            'raw_values': [
                {'value': 'v=DKIM1; k=rsa; p=prawf', 'ttl': 60},
                {'value': 'prawf prawf dyma prawf', 'ttl': 300},
            ],
            'zone': 'unit.tests.',
        }
        test_txt = MythicBeastsProvider._data_for_TXT('', test_data)
        self.assertTrue(isinstance(test_txt, dict))
        self.assertEqual(2, len(test_txt['values']))
        self.assertEqual('v=DKIM1\\; k=rsa\\; p=prawf', test_txt['values'][0])

    def test_data_for_MX(self):
        test_data = {
            'raw_values': [
                {'value': '10 un.unit', 'ttl': 60},
                {'value': '20 dau.unit', 'ttl': 60},
                {'value': '30 tri.unit', 'ttl': 60},
            ],
            'zone': 'unit.tests.',
        }
        test_MX = MythicBeastsProvider._data_for_MX('', test_data)
        self.assertTrue(isinstance(test_MX, dict))
        self.assertEqual(3, len(test_MX['values']))

        with self.assertRaises(AssertionError) as err:
            test_MX = MythicBeastsProvider._data_for_MX(
                '', {'raw_values': [{'value': '', 'ttl': 0}]}
            )
        self.assertEqual('Unable to parse MX data', str(err.exception))

    def test_data_for_CNAME(self):
        test_data = {
            'raw_values': [{'value': 'cname', 'ttl': 60}],
            'zone': 'unit.tests.',
        }
        test_cname = MythicBeastsProvider._data_for_CNAME('', test_data)
        self.assertTrue(isinstance(test_cname, dict))
        self.assertEqual('cname.unit.tests.', test_cname['value'])

    def test_data_for_ANAME(self):
        test_data = {
            'raw_values': [{'value': 'aname', 'ttl': 60}],
            'zone': 'unit.tests.',
        }
        test_aname = MythicBeastsProvider._data_for_ANAME('', test_data)
        self.assertTrue(isinstance(test_aname, dict))
        self.assertEqual('aname', test_aname['value'])

    def test_data_for_SRV(self):
        test_data = {
            'raw_values': [
                {'value': '10 20 30 un.srv.unit', 'ttl': 60},
                {'value': '20 30 40 dau.srv.unit', 'ttl': 60},
                {'value': '30 30 50 tri.srv.unit', 'ttl': 60},
            ],
            'zone': 'unit.tests.',
        }
        test_SRV = MythicBeastsProvider._data_for_SRV('', test_data)
        self.assertTrue(isinstance(test_SRV, dict))
        self.assertEqual(3, len(test_SRV['values']))

        with self.assertRaises(AssertionError) as err:
            test_SRV = MythicBeastsProvider._data_for_SRV(
                '', {'raw_values': [{'value': '', 'ttl': 0}]}
            )
        self.assertEqual('Unable to parse SRV data', str(err.exception))

    def test_data_for_SSHFP(self):
        test_data = {
            'raw_values': [
                {'value': '1 1 0123456789abcdef', 'ttl': 60},
                {'value': '1 2 0123456789abcdef', 'ttl': 60},
                {'value': '2 3 0123456789abcdef', 'ttl': 60},
            ],
            'zone': 'unit.tests.',
        }
        test_SSHFP = MythicBeastsProvider._data_for_SSHFP('', test_data)
        self.assertTrue(isinstance(test_SSHFP, dict))
        self.assertEqual(3, len(test_SSHFP['values']))

        with self.assertRaises(AssertionError) as err:
            test_SSHFP = MythicBeastsProvider._data_for_SSHFP(
                '', {'raw_values': [{'value': '', 'ttl': 0}]}
            )
        self.assertEqual('Unable to parse SSHFP data', str(err.exception))

    def test_data_for_CAA(self):
        test_data = {
            'raw_values': [{'value': '1 issue letsencrypt.org', 'ttl': 60}],
            'zone': 'unit.tests.',
        }
        test_CAA = MythicBeastsProvider._data_for_CAA('', test_data)
        self.assertTrue(isinstance(test_CAA, dict))
        self.assertEqual(3, len(test_CAA['value']))

        with self.assertRaises(AssertionError) as err:
            test_CAA = MythicBeastsProvider._data_for_CAA(
                '', {'raw_values': [{'value': '', 'ttl': 0}]}
            )
        self.assertEqual('Unable to parse CAA data', str(err.exception))

    def test_command_generation(self):
        zone = Zone('unit.tests.', [])
        zone.add_record(
            Record.new(
                zone,
                '',
                {'ttl': 60, 'type': 'ALIAS', 'value': 'alias.unit.tests.'},
            )
        )
        zone.add_record(
            Record.new(
                zone,
                'prawf-ns',
                {
                    'ttl': 300,
                    'type': 'NS',
                    'values': ['alias.unit.tests.', 'alias2.unit.tests.'],
                },
            )
        )
        zone.add_record(
            Record.new(
                zone,
                'prawf-a',
                {'ttl': 60, 'type': 'A', 'values': ['1.2.3.4', '5.6.7.8']},
            )
        )
        zone.add_record(
            Record.new(
                zone,
                'prawf-aaaa',
                {
                    'ttl': 60,
                    'type': 'AAAA',
                    'values': ['a:a::a', 'b:b::b', 'c:c::c:c'],
                },
            )
        )
        zone.add_record(
            Record.new(
                zone,
                'prawf-txt',
                {'ttl': 60, 'type': 'TXT', 'value': 'prawf prawf dyma prawf'},
            )
        )
        zone.add_record(
            Record.new(
                zone,
                'prawf-txt2',
                {
                    'ttl': 60,
                    'type': 'TXT',
                    'value': 'v=DKIM1\\; k=rsa\\; p=prawf',
                },
            )
        )
        with requests_mock() as mock:
            mock.post(ANY, status_code=200, text='')

            provider = MythicBeastsProvider(
                'test', {'unit.tests.': 'mypassword'}
            )

            plan = provider.plan(zone)
            changes = plan.changes
            generated_commands = []

            for change in changes:
                generated_commands.extend(
                    provider._compile_commands('ADD', change.new)
                )

            expected_commands = [
                'ADD unit.tests 60 ANAME alias.unit.tests.',
                'ADD prawf-ns.unit.tests 300 NS alias.unit.tests.',
                'ADD prawf-ns.unit.tests 300 NS alias2.unit.tests.',
                'ADD prawf-a.unit.tests 60 A 1.2.3.4',
                'ADD prawf-a.unit.tests 60 A 5.6.7.8',
                'ADD prawf-aaaa.unit.tests 60 AAAA a:a::a',
                'ADD prawf-aaaa.unit.tests 60 AAAA b:b::b',
                'ADD prawf-aaaa.unit.tests 60 AAAA c:c::c:c',
                'ADD prawf-txt.unit.tests 60 TXT prawf prawf dyma prawf',
                'ADD prawf-txt2.unit.tests 60 TXT v=DKIM1; k=rsa; p=prawf',
            ]

            generated_commands.sort()
            expected_commands.sort()

            self.assertEqual(generated_commands, expected_commands)

            # Now test deletion
            existing = (
                'prawf-txt 300 TXT prawf prawf dyma prawf\n'
                'prawf-txt2 300 TXT v=DKIM1; k=rsa; p=prawf\n'
                'prawf-a 60 A 1.2.3.4'
            )

            with requests_mock() as mock:
                mock.post(ANY, status_code=200, text=existing)
                wanted = Zone('unit.tests.', [])

                plan = provider.plan(wanted)
                changes = plan.changes
                generated_commands = []

                for change in changes:
                    generated_commands.extend(
                        provider._compile_commands('DELETE', change.existing)
                    )

            expected_commands = [
                'DELETE prawf-a.unit.tests 60 A 1.2.3.4',
                'DELETE prawf-txt.unit.tests 300 TXT prawf prawf dyma prawf',
                'DELETE prawf-txt2.unit.tests 300 TXT v=DKIM1; k=rsa; p=prawf',
            ]

            generated_commands.sort()
            expected_commands.sort()

            self.assertEqual(generated_commands, expected_commands)

    def test_fake_command_generation(self):
        class FakeChangeRecord(object):
            def __init__(self):
                self.__fqdn = 'prawf.unit.tests.'
                self._type = 'NOOP'
                self.value = 'prawf'
                self.ttl = 60

            @property
            def record(self):
                return self

            @property
            def fqdn(self):
                return self.__fqdn

        with requests_mock() as mock:
            mock.post(ANY, status_code=200, text='')

            provider = MythicBeastsProvider(
                'test', {'unit.tests.': 'mypassword'}
            )
            record = FakeChangeRecord()
            command = provider._compile_commands('ADD', record)
            self.assertEqual([], command)

    def test_populate(self):
        provider = None

        # Null passwords dict
        with self.assertRaises(AssertionError) as err:
            provider = MythicBeastsProvider('test', None)
        self.assertEqual('Passwords must be a dictionary', str(err.exception))

        # Missing password
        with requests_mock() as mock:
            mock.post(ANY, status_code=401, text='ERR Not authenticated')

            with self.assertRaises(AssertionError) as err:
                provider = MythicBeastsProvider('test', dict())
                zone = Zone('unit.tests.', [])
                provider.populate(zone)
            self.assertEqual(
                'Missing password for domain: unit.tests', str(err.exception)
            )

        # Failed authentication
        with requests_mock() as mock:
            mock.post(ANY, status_code=401, text='ERR Not authenticated')

            with self.assertRaises(Exception) as err:
                provider = MythicBeastsProvider(
                    'test', {'unit.tests.': 'mypassword'}
                )
                zone = Zone('unit.tests.', [])
                provider.populate(zone)
            self.assertEqual(
                'Mythic Beasts unauthorized for zone: unit.tests',
                err.exception.message,
            )

        # Check unmatched lines are ignored
        test_data = 'This should not match'
        with requests_mock() as mock:
            mock.post(ANY, status_code=200, text=test_data)

            provider = MythicBeastsProvider(
                'test', {'unit.tests.': 'mypassword'}
            )
            zone = Zone('unit.tests.', [])
            provider.populate(zone)
            self.assertEqual(0, len(zone.records))

        # Check unsupported records are skipped
        test_data = '@ 60 NOOP prawf\n@ 60 SPF prawf prawf prawf'
        with requests_mock() as mock:
            mock.post(ANY, status_code=200, text=test_data)

            provider = MythicBeastsProvider(
                'test', {'unit.tests.': 'mypassword'}
            )
            zone = Zone('unit.tests.', [])
            provider.populate(zone)
            self.assertEqual(0, len(zone.records))

        # Check no changes between what we support and what's parsed
        # from the unit.tests. config YAML. Also make sure we see the same
        # for both after we've thrown away records we don't support
        with requests_mock() as mock:
            with open('tests/fixtures/mythicbeasts-list.txt') as file_handle:
                mock.post(ANY, status_code=200, text=file_handle.read())

            provider = MythicBeastsProvider(
                'test', {'unit.tests.': 'mypassword'}
            )
            zone = Zone('unit.tests.', [])
            provider.populate(zone)

            self.assertEqual(17, len(zone.records))
            self.assertEqual(17, len(self.expected.records))
            changes = self.expected.changes(zone, provider)
            self.assertEqual(0, len(changes))

    def test_apply(self):
        provider = MythicBeastsProvider(
            'test', {'unit.tests.': 'mypassword'}, strict_supports=False
        )
        zone = Zone('unit.tests.', [])

        # Create blank zone
        with requests_mock() as mock:
            mock.post(ANY, status_code=200, text='')
            provider.populate(zone)

        self.assertEqual(0, len(zone.records))

        # Record change failed
        with requests_mock() as mock:
            mock.post(ANY, status_code=200, text='')
            provider.populate(zone)
            zone.add_record(
                Record.new(
                    zone, 'prawf', {'ttl': 300, 'type': 'TXT', 'value': 'prawf'}
                )
            )
            plan = provider.plan(zone)

        with requests_mock() as mock:
            mock.post(ANY, status_code=400, text='NADD 300 TXT prawf')

            with self.assertRaises(Exception) as err:
                provider.apply(plan)
            self.assertEqual(
                'Mythic Beasts could not action command: unit.tests '
                'ADD prawf.unit.tests 300 TXT prawf',
                err.exception.message,
            )

        # Check deleting and adding/changing test record
        existing = 'prawf 300 TXT prawf prawf prawf\ndileu 300 TXT dileu'

        with requests_mock() as mock:
            mock.post(ANY, status_code=200, text=existing)

            # Mash up a new zone with records so a plan
            # is generated with changes and applied. For some reason
            # passing self.expected, or just changing each record's zone
            # doesn't work. Nor does this without a single add_record after
            wanted = Zone('unit.tests.', [])
            for record in list(self.expected.records):
                data = {'type': record._type}
                data.update(record.data)
                data.pop('octodns', None)
                wanted.add_record(Record.new(wanted, record.name, data))

            wanted.add_record(
                Record.new(
                    wanted,
                    'prawf',
                    {'ttl': 60, 'type': 'TXT', 'value': 'prawf yw e'},
                )
            )

            plan = provider.plan(wanted)

            # Octo ignores NS records (15-1)
            self.assertEqual(
                1, len([c for c in plan.changes if isinstance(c, Update)])
            )
            self.assertEqual(
                1, len([c for c in plan.changes if isinstance(c, Delete)])
            )
            self.assertEqual(
                16, len([c for c in plan.changes if isinstance(c, Create)])
            )
            self.assertEqual(18, provider.apply(plan))
            self.assertTrue(plan.exists)
