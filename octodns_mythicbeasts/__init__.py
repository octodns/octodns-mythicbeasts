from collections.abc import Callable
from logging import getLogger
from typing import Any, ClassVar, cast

from requests import HTTPError, Session

from octodns import __VERSION__ as octodns_version
from octodns.provider import ProviderException
from octodns.provider.base import BaseProvider
from octodns.provider.plan import Plan
from octodns.record import Change, Record
from octodns.record.base import ValueMixin, ValuesMixin
from octodns.zone import Zone

# TODO: remove __VERSION__ with the next major version release
__version__ = __VERSION__ = '3.0.0'


class MythicBeastsZoneNotFoundException(ProviderException):
    pass


class MythicBeastsProvider(BaseProvider):
    SUPPORTS_ROOT_NS = True
    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS: ClassVar[set[str]] = {
        'A',
        'AAAA',
        'ALIAS',
        'CNAME',
        'MX',
        'NS',
        'SRV',
        'SSHFP',
        'CAA',
        'TXT',
        'TLSA',
    }

    MB_API_AUTH_URL: str = 'https://auth.mythic-beasts.com/'
    MB_API_BASE_URL: str = 'https://api.mythic-beasts.com/dns/v2/'

    def _request(
        self,
        method,
        path,
        url=MB_API_BASE_URL,
        params=None,
        data=None,
        json=None,
        auth=None,
        allow_login=True,
    ) -> dict:

        if not self._access_token and allow_login:
            self.log.debug('_request: access_token not set, calling _login()')
            self._login(self._api_key, self._api_secret)

        self.log.debug('_request: method=%s, path=%s', method, path)

        url: str = f'{url}{path}'
        resp = self._sess.request(
            method,
            url,
            params=params,
            data=data,
            json=json,
            timeout=self._timeout,
            auth=auth,
        )
        self.log.debug('_request:   status=%d', resp.status_code)

        if resp.status_code == 401:
            raise ProviderException(
                'Authentication failed for Mythic Beasts API, check your API key and secret'
            )

        try:
            resp.raise_for_status()
        except HTTPError:
            self.log.exception(
                '_request: method=%s, url=%s, response=%s, reason=%s, body=%s',
                method,
                url,
                resp,
                resp.reason,
                resp.text,
            )
            raise

        payload: dict = resp.json()

        return payload

    def _get(self, path, **kwargs) -> dict:
        return self._request('GET', path, **kwargs)

    def _post(self, path, **kwargs) -> dict:
        return self._request('POST', path, **kwargs)

    def _delete(self, path, **kwargs) -> dict:
        return self._request('DELETE', path, **kwargs)

    def _put(self, path, **kwargs) -> dict:
        return self._request('PUT', path, **kwargs)

    def _patch(self, path, **kwargs) -> dict:
        return self._request('PATCH', path, **kwargs)

    def _login(self, api_key, api_secret) -> None:
        """
        Use the Mythic Beasts Auth Service to retrieve an access token.
        """

        resp = self._post(
            url=self.MB_API_AUTH_URL,
            path='login',
            data={'grant_type': 'client_credentials'},
            auth=(api_key, api_secret),
            allow_login=False,
        )

        self._access_token: str = resp['access_token']

        self._sess.headers.update(
            {'Authorization': f'Bearer {self._access_token}'}
        )

    def __init__(self, id, api_key, api_secret, *args, **kwargs) -> None:
        self.log = getLogger(f'MythicBeastsProvider[{id}]')
        self.log.debug(
            '__init__: id=%s, api_key=%s, api_secret=***', id, api_key
        )

        self._timeout = kwargs.pop('timeout', 30)

        super().__init__(id, *args, **kwargs)

        self._sess = Session()
        self._sess.headers.update(
            {
                'User-Agent': f'octodns/{octodns_version} octodns-mythicbeasts/{__VERSION__}'
            }
        )
        self._api_key = api_key
        self._api_secret = api_secret

        self._zones: dict[str, dict] = {}
        self._zone_records: dict[str, list[dict]] = {}

        self._access_token: str | None = None

    @property
    def zones(self) -> dict[str, dict]:
        if not self._zones:

            zone_response: dict = self._get(path='zones')

            zone_list: list[str] = zone_response.get('zones', [])

            for zone in zone_list:
                zone_name: str = _normalise_zone_name(zone)

                self._zones[zone_name] = {'name': zone_name}
        return self._zones

    def zone_records(self, zone: Zone) -> list[dict]:
        zone_name: str = str(zone.name)

        if zone_name not in self._zone_records:
            if zone_name not in self.zones:
                return []

            normalized_zone_name = zone_name.removesuffix('.')

            record_response: dict = self._get(
                path=f'zones/{normalized_zone_name}/records',
                params={'exclude-generated': 'true'},
            )

            record_response_list: list[dict] = record_response.get(
                'records', []
            )
            records = list(record_response_list)

            self._zone_records[zone_name] = records

        return self._zone_records[zone_name]

    def _record_for(
        self,
        zone: str,
        name: str,
        _type: str,
        records: list[dict],
        lenient: bool,
    ) -> Record:
        data_for: Callable[[str, list[dict]], dict] = getattr(
            self, f'_data_for_{_type}'
        )
        data: dict | list = data_for(_type, records)
        record: Record = Record.new(
            zone, name, data, source=self, lenient=lenient
        )
        return record

    def _data_for_multiple(self, _type, records: list[dict]) -> dict:
        return {
            'ttl': records[0].get('ttl'),
            'type': _type,
            'values': [record.get('data') for record in records],
        }

    def _data_for_single(self, _type, records: list[dict]) -> dict:
        return {
            'ttl': records[0].get('ttl'),
            'type': _type,
            'value': records[0].get('data'),
        }

    def _data_for_MX(self, _type, records: list[dict]) -> dict:
        return {
            'ttl': records[0].get('ttl'),
            'type': _type,
            'values': [
                {
                    'exchange': record.get('data'),
                    'preference': record.get('mx_priority'),
                }
                for record in records
            ],
        }

    def _data_for_SRV(self, _type, records: list[dict]) -> dict:
        return {
            'ttl': records[0].get('ttl'),
            'type': _type,
            'values': [
                {
                    'target': record.get('data'),
                    'priority': record.get('srv_priority'),
                    'weight': record.get('srv_weight'),
                    'port': record.get('srv_port'),
                }
                for record in records
            ],
        }

    def _data_for_TXT(self, _type, records: list[dict]) -> dict:
        return {
            'ttl': records[0].get('ttl'),
            'type': _type,
            'values': [
                str(record.get('data')).replace(';', '\\;')
                for record in records
            ],
        }

    def _data_for_SSHFP(self, _type, records: list[dict]) -> dict:
        return {
            'ttl': records[0].get('ttl'),
            'type': _type,
            'values': [
                {
                    'fingerprint': record.get('data'),
                    'algorithm': record.get('sshfp_algorithm'),
                    'fingerprint_type': record.get('sshfp_type'),
                }
                for record in records
            ],
        }

    def _data_for_TLSA(self, _type, records: list[dict]) -> dict:
        return {
            'ttl': records[0].get('ttl'),
            'type': _type,
            'values': [
                {
                    'certificate_usage': record.get('tlsa_usage'),
                    'selector': record.get('tlsa_selector'),
                    'matching_type': record.get('tlsa_matching'),
                    'certificate_association_data': record.get('data'),
                }
                for record in records
            ],
        }

    def _data_for_CAA(self, _type, records: list[dict]) -> dict:
        return {
            'ttl': records[0].get('ttl'),
            'type': _type,
            'values': [
                {
                    'flags': record.get('caa_flags'),
                    'tag': record.get('caa_tag'),
                    'value': record.get('data'),
                }
                for record in records
            ],
        }

    _data_for_A = _data_for_multiple
    _data_for_AAAA = _data_for_multiple
    _data_for_NS = _data_for_multiple
    _data_for_CNAME = _data_for_single
    _data_for_ALIAS = _data_for_single

    def populate(self, zone, target=False, lenient=False):
        self.log.debug(
            'populate: name=%s, target=%s, lenient=%s',
            zone.name,
            target,
            lenient,
        )

        exists = zone.name in self.zones
        before_length: int = len(zone.records)
        records: list[dict] = self.zone_records(zone)

        if records:
            values: dict[str, dict[str, list[dict]]] = {}
            for record in records:
                record_name: str = _normalise_record_name(record['host'])
                record_type: str = record['type']

                if record_type == 'ANAME':
                    record_type = 'ALIAS'

                if record_type == 'SOA':
                    self.log.info(
                        'populate:   skipping SOA record for %s', record_name
                    )
                    continue

                if record_type not in self.SUPPORTS:
                    self.log.warning(
                        'populate: ignoring record with unsupported rrtype, %s  %s',
                        record_name,
                        record_type,
                    )
                    continue

                if record_name not in values:
                    values[record_name] = {}
                values[record_name].setdefault(record_type, []).append(record)

            for name, types in values.items():
                for record_type, records in types.items():
                    record: Record = self._record_for(
                        zone, name, record_type, records, lenient
                    )
                    zone.add_record(record, lenient=lenient)

        self.log.info(
            'populate:   found %s records, exists=%s',
            len(zone.records) - before_length,
            exists,
        )
        return exists

    def _apply(self, plan: Plan):
        desired: Zone = plan.desired
        changes: list[Change] = plan.changes

        self.log.debug(
            '_apply: zone=%s, len(changes)=%d', desired.name, len(changes)
        )

        name = desired.name

        # Mythic Beasts do not support creating zones via the API.
        if name not in self.zones:
            self.log.error(
                '_apply: zone %s does not exist in Mythic Beasts, '
                'cannot create via API',
                name,
            )
            raise MythicBeastsZoneNotFoundException(
                f'zone {name} does not exist in Mythic Beasts account, '
                'please create the zone manually in the Mythic Beasts control panel'
            )

        for change in changes:
            class_name: str = change.__class__.__name__
            getattr(self, f'_apply_{class_name}')(change)

        # Clear the cache
        self._zone_records.pop(name, None)

    def _contents_for_single(
        self, record: Record, record_name: str, record_type: str
    ) -> dict[str, list]:

        single = cast(ValueMixin, record)
        contents: dict[str, list] = {
            'records': [
                {
                    'host': record_name,
                    'type': record_type,
                    'ttl': record.ttl,
                    'data': single.value,
                }
            ]
        }

        return contents

    def _contents_for_multiple(
        self, record: Record, record_name: str, record_type: str
    ) -> dict[str, list]:

        multiple = cast(ValuesMixin, record)
        contents: dict[str, list] = {
            'records': [
                {
                    'host': record_name,
                    'type': record_type,
                    'ttl': record.ttl,
                    'data': value,
                }
                for value in multiple.values
            ]
        }

        return contents

    def _contents_for_MX(
        self, record: Record, record_name: str, record_type: str
    ) -> dict[str, list]:

        multiple = cast(ValuesMixin, record)
        contents: dict[str, list] = self._contents_for_multiple(
            record, record_name, record_type
        )
        for i, value in enumerate(multiple.values):
            contents['records'][i]['mx_priority'] = value['preference']
            contents['records'][i]['data'] = value['exchange']
        return contents

    def _contents_for_SRV(
        self, record: Record, record_name: str, record_type: str
    ) -> dict[str, list]:

        multiple = cast(ValuesMixin, record)
        contents: dict[str, list] = self._contents_for_multiple(
            record, record_name, record_type
        )
        for i, value in enumerate(multiple.values):
            contents['records'][i]['srv_priority'] = value['priority']
            contents['records'][i]['srv_weight'] = value['weight']
            contents['records'][i]['srv_port'] = value['port']
            contents['records'][i]['data'] = value['target']
        return contents

    def _contents_for_SSHFP(
        self, record: Record, record_name: str, record_type: str
    ) -> dict[str, list]:

        multiple = cast(ValuesMixin, record)
        contents: dict[str, list] = self._contents_for_multiple(
            record, record_name, record_type
        )
        for i, value in enumerate(multiple.values):
            contents['records'][i]['sshfp_algorithm'] = value['algorithm']
            contents['records'][i]['sshfp_type'] = value['fingerprint_type']
            contents['records'][i]['data'] = value['fingerprint']
        return contents

    def _contents_for_TLSA(
        self, record: Record, record_name: str, record_type: str
    ) -> dict[str, list]:

        multiple = cast(ValuesMixin, record)
        contents: dict[str, list] = self._contents_for_multiple(
            record, record_name, record_type
        )
        for i, value in enumerate(multiple.values):
            contents['records'][i]['tlsa_usage'] = value['certificate_usage']
            contents['records'][i]['tlsa_selector'] = value['selector']
            contents['records'][i]['tlsa_matching'] = value['matching_type']
            contents['records'][i]['data'] = value[
                'certificate_association_data'
            ]
        return contents

    def _contents_for_CAA(
        self, record: Record, record_name: str, record_type: str
    ) -> dict[str, list]:

        multiple = cast(ValuesMixin, record)
        contents: dict[str, list] = self._contents_for_multiple(
            record, record_name, record_type
        )
        for i, value in enumerate(multiple.values):
            contents['records'][i]['caa_flags'] = value['flags']
            contents['records'][i]['caa_tag'] = value['tag']
            contents['records'][i]['data'] = value['value']
        return contents

    def _contents_for_TXT(
        self, record: Record, record_name: str, record_type: str
    ) -> dict[str, list]:

        multiple = cast(ValuesMixin, record)
        contents: dict[str, list] = self._contents_for_multiple(
            record, record_name, record_type
        )
        for i, value in enumerate(multiple.values):
            # reverse the escaping applied in _data_for_TXT before sending to the API
            contents['records'][i]['data'] = value.replace('\\;', ';')
        return contents

    _contents_for_ALIAS = _contents_for_single
    _contents_for_A = _contents_for_multiple
    _contents_for_AAAA = _contents_for_multiple
    _contents_for_CNAME = _contents_for_single
    _contents_for_NS = _contents_for_multiple

    def _gen_data(self, record: Record):

        zone_name, record_name, record_type = _normalise_content(record)
        path: str = f'zones/{zone_name}/records/{record_name}/{record_type}'
        record_type_name: str = cast(str, cast(Any, record)._type)

        contents_for: Callable[[Record, str, str], dict[str, list]] = getattr(
            self, f'_contents_for_{record_type_name}'
        )
        content: dict[str, list] = contents_for(
            record, record_name, record_type
        )

        return path, content

    def _apply_Create(self, change: Change) -> None:
        new = change.new
        self.log.debug(
            '_apply_Create:  name=%s type=%s ttl=%s',
            new.name,
            new._type,
            new.ttl,
        )

        path, content = self._gen_data(new)
        self._post(path, json=content)

    def _apply_Update(self, change: Change) -> None:
        new: Record = change.new
        record_type_name: str = cast(str, cast(Any, new)._type)
        self.log.debug(
            '_apply_Update:  name=%s type=%s ttl=%s',
            new.name,
            record_type_name,
            new.ttl,
        )

        path, content = self._gen_data(new)
        self.log.debug(path)
        self.log.debug(content)
        self._put(path, json=content)

    def _apply_Delete(self, change: Change) -> None:
        existing = change.existing
        self.log.debug(
            '_apply_Delete:  name=%s type=%s', existing.name, existing._type
        )

        path, _ = self._gen_data(existing)
        self._delete(path, params={'exclude-generated': 'true'})


def _normalise_content(record: Record) -> tuple[str, str, str]:
    """
    Ensure both octodns and Mythic Beasts are working with the same content format.
    """

    zone_name: str = record.zone.name.removesuffix('.')
    record_name: str = record.name
    record_type: str = cast(str, cast(Any, record)._type)

    # Mythic Beasts uses an '@' for the apex record name, but octodns uses an empty string.
    if record_name == '':
        record_name = '@'

    # Mythic Beasts uses 'ANAME' for the octodns 'ALIAS' type.
    if record_type == 'ALIAS':
        record_type = 'ANAME'

    return zone_name, record_name, record_type


def _normalise_zone_name(name: str) -> str:
    """
    Ensure both octodns and Mythic Beasts are working with the same zone name format.
    """
    if not name.endswith('.'):
        name += '.'
    return name


def _normalise_record_name(name: str) -> str:
    """
    Ensure both octodns and Mythic Beasts are working with the same record name format.
    """
    if name == '@':
        name = ''
    return name
