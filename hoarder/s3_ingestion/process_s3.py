#this process the json and writes it directly into the database, any new entries will make a new column. It will not go through the django models

from django.core.management.base import BaseCommand
from django.db import models
from s3_ingestion.models import RawS3
from s3_ingestion import models as s3models

import boto3
import json
import zlib

import datetime
import functools
import itertools
import math
import re
from typing import NamedTuple


def jsonparser_return_dict(json_obj,filename="")->None: #parse the json and makes the entries in appropriate tables in postgres
    assert(isinstance(json_obj, dict)), "Expected a dict at the top level of the JSON object"
    assert (isinstance(filename, str)), "Expected filename to be a string"
    
    pconnect=connect_postgres()

    list_dict_gateway=list()
    list_dict_battery_error_info=list()
    list_dict_battery_modules=list()
    
    
    #checks if any of the keys in the json is a time stamp example "2025-05-13 14:23:17.200195349"    
    if isinstance(json_obj, dict):
        for key, value in json_obj.items():
            result=re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+", key)
            if result:
                print("Found timestamp key: %r:" % (key))

                #load the sub json_dict
                timestampentry=json_obj[key]
                #check if subjson is dict:
                #print type of subjson                
                if (isinstance(timestampentry, list)):

                    for tentry in timestampentry:
                        if isinstance(tentry, dict):
                            if "GW_UID" in tentry:
                                print("Found GW_UID key: %r:" % (tentry["GW_UID"]))
                                #form an empty dict to be ready to insert into postgres gateway_events
                                gateway_event={}
                                gateway_event["GW_UID"]=tentry["GW_UID"]
                                gateway_event["event_timestamp"]=key #timestamp
                                gateway_event["filename"]=filename
                                for subkey, subvalue in tentry.items():
                                    if subkey=="BATTERY_ERROR_INFO":
                                        temp_battery_error=parse_battery_error(subvalue,filename,tentry["GW_UID"])
                                        list_dict_battery_error_info.extend(temp_battery_error) #this will go into battery error info table in postgres                                        
                                        pass #this will go into battery error info table in postgres
                                    elif subkey=="BATTERY_MODULES":
                                        pass #this will go into battery modules table in postgres
                                    elif re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+", subkey):
                                        tempgateway,tempbatterror,tempbatter_modules=jsonparser_return_dict(tentry) #recursive call to parse the sub json with timestamp key
                                        list_dict_gateway.extend(tempgateway)
                                        list_dict_battery_error_info.extend(tempbatterror)
                                        list_dict_battery_modules.extend(tempbatter_modules)
                                    else:
                                        gateway_event[subkey]=subvalue                                
                                print (gateway_event)
                                #insert dict in gateway_events
                                list_dict_gateway.append(gateway_event)

                        else:
                            assert(False), "did not get a dict?!?"

    return list_dict_gateway, list_dict_battery_error_info, list_dict_battery_modules


# ---------------------------------------------------------------------------
# parse_raw_json(): RawS3.rawjson -> list of dicts for every table in models.py
#
# Each dict uses the model's field names, so a row can be saved with
#   TABLE_MODELS[name].objects.bulk_create([TABLE_MODELS[name](**d) for d in rows])
# json keys that have no column (or a value that does not fit the column type)
# are kept in the row's 'extra' dict, so nothing in the json is dropped.
# ---------------------------------------------------------------------------

class ParsedTables(NamedTuple):
    gateway_file_info: list
    gateway_interface: list
    error_log_message: list
    gateway_poll: list
    export_event: list
    zigbee_device: list
    operation_status: list
    eastron_meter_phase: list
    battery_error_info: list
    battery_error_fault_history: list
    battery_error_lg_module: list
    battery_module_reading: list
    battery_diagnostic: list
    battery_diagnostic_module: list
    openadr_event: list
    openadr_stack_entry: list
    openadr_log_data: list
    muc_node: list
    muc_node_error: list
    muc_inverter_data: list
    muc_battery_data: list
    muc_battery_module: list


#ParsedTables field name -> model class
TABLE_MODELS={
    'gateway_file_info': s3models.GatewayFileInfo,
    'gateway_interface': s3models.GatewayInterface,
    'error_log_message': s3models.ErrorLogMessage,
    'gateway_poll': s3models.GatewayPoll,
    'export_event': s3models.ExportEvent,
    'zigbee_device': s3models.ZigbeeDevice,
    'operation_status': s3models.OperationStatus,
    'eastron_meter_phase': s3models.EastronMeterPhase,
    'battery_error_info': s3models.BatteryErrorInfo,
    'battery_error_fault_history': s3models.BatteryErrorFaultHistory,
    'battery_error_lg_module': s3models.BatteryErrorLgModule,
    'battery_module_reading': s3models.BatteryModuleReading,
    'battery_diagnostic': s3models.BatteryDiagnostic,
    'battery_diagnostic_module': s3models.BatteryDiagnosticModule,
    'openadr_event': s3models.OpenAdrEvent,
    'openadr_stack_entry': s3models.OpenAdrStackEntry,
    'openadr_log_data': s3models.OpenAdrLogData,
    'muc_node': s3models.MucNode,
    'muc_node_error': s3models.MucNodeError,
    'muc_inverter_data': s3models.MucInverterData,
    'muc_battery_data': s3models.MucBatteryData,
    'muc_battery_module': s3models.MucBatteryModule,
}
assert set(TABLE_MODELS)==set(ParsedTables._fields), "TABLE_MODELS and ParsedTables are out of sync"


POLL_TIMESTAMP_RE=re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+$")
_TIMESTAMP_RE=re.compile(r"^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(?:\.(\d+))?Z?$")

#keys inside a poll entry that hold nested json and get their own tables
POLL_NESTED_KEYS={'BATTERY_ERROR_INFO','BATTERY_MODULES','EXPORT_EVENTS','ZB_DEVICES','OPERATION_STATUSES',
                  'EASTRON_METERS_INFO','OPENADR_EVENT_LOG','battery_diagnostic','NODES'}

#columns the json is never allowed to write into
_PROTECTED_COLUMNS={'id','raw','raw_id','filename','extra'}


def parse_timestamp(value):
    """'YYYY-MM-DD HH:MM:SS.nnnnnnnnn', 'YYYY-MM-DDTHH:MM:SSZ' or epoch seconds -> aware UTC datetime, None if it can't be parsed."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.datetime.fromtimestamp(value, tz=datetime.timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        m=_TIMESTAMP_RE.match(value.strip())
        if m:
            fraction=(m.group(3) or '')[:6].ljust(6, '0') #python datetime only has microseconds
            try:
                return datetime.datetime.fromisoformat(f"{m.group(1)}T{m.group(2)}.{fraction}+00:00")
            except ValueError:
                return None
    return None


def _column_name(key):
    #"MAX CELL VDC" -> "max_cell_vdc", "Wi-Fi" -> "wi_fi"
    return re.sub(r'[^0-9a-z]+', '_', str(key).lower()).strip('_')


def _clean_json(value):
    #NaN / Infinity are not valid in a JSONField
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: _clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean_json(v) for v in value]
    return value


_NOT_CONVERTED=object()

def _convert(field, value):
    """Convert a json value to the field's type. Returns _NOT_CONVERTED if it does not fit."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return _NOT_CONVERTED

    if isinstance(field, models.BooleanField):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and value in (0, 1):
            return bool(value)
        return _NOT_CONVERTED

    if isinstance(field, models.IntegerField): #includes BigIntegerField
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value) if value.is_integer() else _NOT_CONVERTED
        if isinstance(value, str):
            s=value.strip()
            try:
                return int(s, 16) if s.lower().startswith('0x') else int(s)
            except ValueError:
                try:
                    f=float(s)
                    return int(f) if f.is_integer() else _NOT_CONVERTED
                except ValueError:
                    return _NOT_CONVERTED
        return _NOT_CONVERTED

    if isinstance(field, models.FloatField):
        try:
            f=float(value) #handles int, bool and numeric strings like "1.500000"
        except (TypeError, ValueError):
            return _NOT_CONVERTED
        return f if math.isfinite(f) else None

    if isinstance(field, models.DateTimeField):
        dt=parse_timestamp(value)
        return dt if dt is not None else _NOT_CONVERTED

    if isinstance(field, (models.CharField, models.TextField)):
        s=str(value)
        if field.max_length is not None and len(s)>field.max_length:
            return _NOT_CONVERTED
        return s

    return value


@functools.lru_cache(maxsize=None)
def _model_columns(model):
    return {f.name: f for f in model._meta.concrete_fields if f.name not in _PROTECTED_COLUMNS}


def _build_row(model, data, base, rename=None):
    """
    data: json dict for one row. base: values already known (raw_id, filename, gw_uid, poll_timestamp, indexes...).
    Returns a dict with the model's field names. Keys without a column go to row['extra'].
    """
    row=dict(base)
    extra={}
    columns=_model_columns(model)
    for key, value in data.items():
        column=(rename or {}).get(key) or _column_name(key)
        field=columns.get(column)
        if field is None:
            extra[key]=value
            continue
        converted=_convert(field, value)
        if converted is _NOT_CONVERTED:
            extra[key]=value
        elif column in base:
            if converted!=base[column]:
                extra[key]=value #json disagrees with a value we set, keep both
        else:
            row[column]=converted
    row['extra']=_clean_json(extra) if extra else None
    return row


def _to_int(value):
    converted=_convert(models.BigIntegerField(), value)
    return None if converted is _NOT_CONVERTED else converted


def _file_gw_uid(rawjson, filename):
    #gw uid from the first poll entry, or from the filename "<uid>_<date>.json.bin"
    for key, value in rawjson.items():
        if POLL_TIMESTAMP_RE.match(key) and isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict) and isinstance(entry.get('GW_UID'), str):
                    return entry['GW_UID']
    name=filename.rsplit('/', 1)[-1]
    return name.split('_', 1)[0] if '_' in name else None


def _parse_battery_errors(errors, base, tables, error_counter, source, node_id=None):
    for error in errors:
        if not isinstance(error, dict):
            continue
        error_index=next(error_counter)
        flat={k: v for k, v in error.items() if k not in ('FAULT_HISTORY', 'LG_MODULES') or not isinstance(v, list)}
        tables.battery_error_info.append(_build_row(s3models.BatteryErrorInfo, flat,
                                                    {**base, 'source': source, 'node_id': node_id, 'error_index': error_index}))
        child_base={**base, 'error_index': error_index}
        for item in error.get('FAULT_HISTORY') if isinstance(error.get('FAULT_HISTORY'), list) else []:
            if isinstance(item, dict):
                tables.battery_error_fault_history.append(_build_row(s3models.BatteryErrorFaultHistory, item, child_base))
        for item in error.get('LG_MODULES') if isinstance(error.get('LG_MODULES'), list) else []:
            if isinstance(item, dict):
                tables.battery_error_lg_module.append(_build_row(s3models.BatteryErrorLgModule, item, child_base))


def _parse_battery_modules(value, base, tables):
    battery_type=value.get('TYPE')
    for reading_index, reading in enumerate(value.get('READINGS') or []):
        if not isinstance(reading, dict):
            continue
        if isinstance(reading.get('SERIAL_NUMBER'), list):
            reading={**reading, 'SERIAL_NUMBER': ','.join(str(s) for s in reading['SERIAL_NUMBER'])}
        tables.battery_module_reading.append(_build_row(s3models.BatteryModuleReading, reading,
                                                        {**base, 'battery_type': battery_type, 'reading_index': reading_index}))


def _parse_eastron(value, base, tables):
    frequency=value.get('FREQUENCY')
    for meter_key, meter in value.items():
        if not isinstance(meter, dict):
            continue
        for phase_key, phase in meter.items():
            if not isinstance(phase, dict):
                continue
            m=re.search(r'(\d+)$', phase_key)
            tables.eastron_meter_phase.append(_build_row(s3models.EastronMeterPhase, {**phase, 'FREQUENCY': frequency},
                                                         {**base, 'meter': meter_key.removeprefix('EASTRON_'),
                                                          'phase': int(m.group(1)) if m else None}))


def _parse_openadr(events, base, tables):
    for event_index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        flat={k: v for k, v in event.items() if k not in ('OADR_STACK', 'LOG_DATA') or not isinstance(v, list)}
        tables.openadr_event.append(_build_row(s3models.OpenAdrEvent, flat, {**base, 'event_index': event_index}))
        child_base={**base, 'event_index': event_index}
        for item in event.get('OADR_STACK') if isinstance(event.get('OADR_STACK'), list) else []:
            if isinstance(item, dict):
                tables.openadr_stack_entry.append(_build_row(s3models.OpenAdrStackEntry, item, child_base))
        for item in event.get('LOG_DATA') if isinstance(event.get('LOG_DATA'), list) else []:
            if isinstance(item, dict):
                tables.openadr_log_data.append(_build_row(s3models.OpenAdrLogData, item, child_base))


def _parse_battery_diagnostic(value, base, tables):
    modules=value.get('BATTERY_MODULES')
    flat={k: v for k, v in value.items() if k!='BATTERY_MODULES' or not isinstance(v, list)}
    tables.battery_diagnostic.append(_build_row(s3models.BatteryDiagnostic, flat, base))
    for module_index, module in enumerate(modules if isinstance(modules, list) else []):
        if isinstance(module, dict):
            tables.battery_diagnostic_module.append(_build_row(s3models.BatteryDiagnosticModule, module,
                                                               {**base, 'module_index': module_index}))


def _parse_muc_nodes(nodes, base, tables, error_counter):
    nested_keys=('ERRORS', 'INVERTER_ERROR', 'INVERTER_DATA', 'BATTERY_DATA')
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id=_to_int(node.get('NODE_ID'))
        battery_type=node.get('BATTERY_TYPE')
        flat={k: v for k, v in node.items() if k not in nested_keys or not isinstance(v, (dict, list))}
        tables.muc_node.append(_build_row(s3models.MucNode, flat, base))

        node_base={**base, 'node_id': node_id}
        if isinstance(node.get('ERRORS'), list):
            for item in node['ERRORS']:
                if isinstance(item, dict):
                    tables.muc_node_error.append(_build_row(s3models.MucNodeError, item, node_base))
        if isinstance(node.get('INVERTER_ERROR'), list):
            _parse_battery_errors(node['INVERTER_ERROR'], base, tables, error_counter, 'INVERTER_ERROR', node_id)
        if isinstance(node.get('INVERTER_DATA'), dict):
            tables.muc_inverter_data.append(_build_row(s3models.MucInverterData, node['INVERTER_DATA'], node_base))
        if isinstance(node.get('BATTERY_DATA'), dict):
            battery_data=node['BATTERY_DATA']
            modules=battery_data.get('BATTERY_MODULES')
            flat={k: v for k, v in battery_data.items() if k!='BATTERY_MODULES' or not isinstance(v, list)}
            tables.muc_battery_data.append(_build_row(s3models.MucBatteryData, flat, {**node_base, 'battery_type': battery_type}))
            for module_index, module in enumerate(modules if isinstance(modules, list) else []):
                if isinstance(module, dict):
                    tables.muc_battery_module.append(_build_row(s3models.MucBatteryModule, module,
                                                                {**node_base, 'battery_type': battery_type, 'module_index': module_index}))


def _parse_poll(poll_key, entry, file_base, tables):
    gw_uid=entry.get('GW_UID') if isinstance(entry.get('GW_UID'), str) else file_base['gw_uid']
    base={**file_base, 'gw_uid': gw_uid, 'poll_timestamp': parse_timestamp(poll_key)}

    flat={}
    nested={}
    for key, value in entry.items():
        if key in POLL_NESTED_KEYS and isinstance(value, (dict, list)):
            nested[key]=value
        else:
            flat[key]=value
    tables.gateway_poll.append(_build_row(s3models.GatewayPoll, flat, {**base, 'poll_timestamp_raw': poll_key}))

    error_counter=itertools.count() #error_index is unique per poll across BATTERY_ERROR_INFO and INVERTER_ERROR
    for key, value in nested.items():
        if key=='BATTERY_ERROR_INFO' and isinstance(value, list):
            _parse_battery_errors(value, base, tables, error_counter, 'BATTERY_ERROR_INFO')
        elif key=='BATTERY_MODULES' and isinstance(value, dict):
            _parse_battery_modules(value, base, tables)
        elif key=='EXPORT_EVENTS' and isinstance(value, list):
            tables.export_event.extend(_build_row(s3models.ExportEvent, item, base) for item in value if isinstance(item, dict))
        elif key=='ZB_DEVICES' and isinstance(value, list):
            tables.zigbee_device.extend(_build_row(s3models.ZigbeeDevice, item, base, rename={'ID': 'device_id'})
                                        for item in value if isinstance(item, dict))
        elif key=='OPERATION_STATUSES' and isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    data=item.get('DATA')
                    flat_item={k: v for k, v in item.items() if k!='DATA' or not isinstance(v, dict)}
                    if isinstance(data, dict):
                        flat_item.update({f'DATA_{k}': v for k, v in data.items()})
                    tables.operation_status.append(_build_row(s3models.OperationStatus, flat_item, base))
        elif key=='EASTRON_METERS_INFO' and isinstance(value, dict):
            _parse_eastron(value, base, tables)
        elif key=='OPENADR_EVENT_LOG' and isinstance(value, list):
            _parse_openadr(value, base, tables)
        elif key=='battery_diagnostic' and isinstance(value, dict):
            _parse_battery_diagnostic(value, base, tables)
        elif key=='NODES' and isinstance(value, list):
            _parse_muc_nodes(value, base, tables, error_counter)
        else:
            #nested key with an unexpected shape, keep it on the poll row
            poll_row=tables.gateway_poll[-1]
            poll_row['extra']={**(poll_row['extra'] or {}), key: _clean_json(value)}


def parse_raw_json(rawjson: dict, filename: str, raw_id: int | None = None) -> ParsedTables:
    """
    Parse one RawS3.rawjson into rows for every table in models.py.

    rawjson:  the decoded gateway json (RawS3.rawjson)
    filename: json filename, stored in every row (RawS3.filename)
    raw_id:   RawS3.id the rows link back to (can be None for testing, but must be set before saving)

    Returns a ParsedTables named tuple; each field is a list of dicts for that table, e.g.
        tables=parse_raw_json(raw.rawjson, raw.filename, raw.id)
        tables.gateway_poll, tables.battery_error_info, ...
    """
    assert isinstance(rawjson, dict), f"rawjson must be a dict, got {type(rawjson).__name__}"
    assert isinstance(filename, str) and filename, f"filename must be a non-empty str, got {filename!r}"
    assert raw_id is None or isinstance(raw_id, int), f"raw_id must be an int or None, got {raw_id!r}"

    tables=ParsedTables(*([] for _ in ParsedTables._fields))
    file_base={'raw_id': raw_id, 'filename': filename, 'gw_uid': _file_gw_uid(rawjson, filename), 'poll_timestamp': None}

    file_info={}
    for key, value in rawjson.items():
        if POLL_TIMESTAMP_RE.match(key) and isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    _parse_poll(key, entry, file_base, tables)
        elif key=='INTERFACES' and isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    for interface, status in item.items():
                        tables.gateway_interface.append(_build_row(s3models.GatewayInterface,
                                                                   {'INTERFACE': interface, 'STATUS': status}, file_base))
        elif key=='ERROR_LOGS' and isinstance(value, dict):
            uid=value.get('UID')
            messages=value.get('MESSAGES')
            for message in messages if isinstance(messages, list) else []:
                if isinstance(message, dict):
                    tables.error_log_message.append(_build_row(s3models.ErrorLogMessage, {**message, 'UID': uid}, file_base))
        else:
            file_info[key]=value #LED_ASPECT, ETHERNET_MAC and anything new
    tables.gateway_file_info.append(_build_row(s3models.GatewayFileInfo, file_info, file_base))

    return tables





def parsedtables_to_models(tables: ParsedTables):
    """Save the parsed rows from parse_raw_json() into their Django models.

    Each field in ParsedTables is a list of row dicts for one database table.
    The dicts already contain the values for each model field, including the
    foreign-key raw_id and extra JSON payload.
    """
    if not isinstance(tables, ParsedTables):
        raise TypeError(f"tables must be a ParsedTables instance, got {type(tables).__name__}")

    created_by_table = {}
    for table_name, model in TABLE_MODELS.items():
        rows = getattr(tables, table_name)
        if not rows:
            created_by_table[table_name] = 0
            continue

        model_instances = [model(**row) for row in rows]
        model.objects.bulk_create(model_instances)
        created_by_table[table_name] = len(model_instances)

    return created_by_table
