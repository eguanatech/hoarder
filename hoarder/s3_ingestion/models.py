from django.db import models
from django.utils import timezone
from datetime import datetime



class RawS3(models.Model):
    filename=models.CharField(max_length=500)
    s3_bucket=models.CharField(max_length=500)
    pathfilename=models.CharField(max_length=500, unique=True)
    rawjson=models.JSONField()
    date=models.DateTimeField(default=datetime.fromisoformat('1970-01-01T00:00:00+00:00')) #date processed. filename can have date local date of json



# ---------------------------------------------------------------------------
# Tables parsed out of RawS3.rawjson (gateway PDR json, see egear-gateway2)
#
# Column names are the json keys in lower case (spaces -> '_'), so a key in
# the json can be found in the table by lower-casing it.
# Every column is nullable because older firmware does not send newer keys.
# Any json key that has no column here is kept in that row's 'extra' column.
# ---------------------------------------------------------------------------

def _float():
    return models.FloatField(null=True, blank=True)

def _int():
    return models.BigIntegerField(null=True, blank=True)

def _bool():
    return models.BooleanField(null=True, blank=True)

def _char(max_length=255):
    return models.CharField(max_length=max_length, null=True, blank=True)

def _text():
    return models.TextField(null=True, blank=True)

def _datetime():
    return models.DateTimeField(null=True, blank=True)


class GatewayDataBase(models.Model):
    raw=models.ForeignKey(RawS3, on_delete=models.CASCADE)
    filename=models.CharField(max_length=500)
    gw_uid=models.CharField(max_length=64, null=True, blank=True, db_index=True)
    poll_timestamp=models.DateTimeField(null=True, blank=True, db_index=True) #the "YYYY-MM-DD HH:MM:SS.nnnnnnnnn" key the row came from (UTC). null for file level tables
    extra=models.JSONField(null=True, blank=True) #json keys that have no column in this table

    class Meta:
        abstract=True


# ---- file level (top level keys that are not poll timestamps) -------------

class GatewayFileInfo(GatewayDataBase):
    led_aspect=_char()
    ethernet_mac=_char(64)

    class Meta:
        db_table='gateway_file_info'


class GatewayInterface(GatewayDataBase): #INTERFACES: [{"ETHERNET": "ACTIVE-SELECTED", "WIFI": "INACTIVE", ...}], one row per interface
    interface=_char(64)
    status=_char(64)

    class Meta:
        db_table='gateway_interface'


class ErrorLogMessage(GatewayDataBase): #ERROR_LOGS.MESSAGES[]
    uid=_char(64)
    timestamp=_datetime()
    log_level=_int()
    message=_text()

    class Meta:
        db_table='error_log_message'


# ---- poll level: one row per "<timestamp>": [{...}] entry ------------------

class GatewayPoll(GatewayDataBase):
    poll_timestamp_raw=_char(40) #original key, keeps the nanoseconds

    json_version=_char(16)
    gw_loc_code=_int()
    gw_sw_vers=_char(64)
    hw_type=_char(64)
    scheduled_poll=_bool()
    modem_imei=_char(64)
    sim_iccid=_char(64)

    #gateway health drone
    gw_temp=_float()
    gw_temp_fault_code=_int()
    gw_batt_level=_float()
    gw_batt_level_fault_code=_int()
    gw_on_batt=_float()
    gw_on_batt_fault_code=_int()
    gw_batt_discon=_float()
    gw_batt_discon_fault_code=_int()
    gw_mem_use=_float()
    gw_mem_use_fault_code=_int()
    gw_fs_use_1=_float()
    gw_fs_use_1_fault_code=_int()
    gw_fs_use_2=_float()
    gw_fs_use_2_fault_code=_int()
    gw_fs_use_3=_float()
    gw_fs_use_3_fault_code=_int()
    gw_fs_use_4=_float()
    gw_fs_use_4_fault_code=_int()
    gw_sim_discon=_float()
    gw_sim_discon_fault_code=_int()
    gw_sd_discon=_float()
    gw_sd_discon_fault_code=_int()

    #transformer drone (power / energy)
    freq=_float()
    freq_fault_code=_int()
    voltage=_float()
    voltage_fault_code=_int()
    vars=_float()
    vars_fault_code=_int()
    load_power=_float()
    load_power_fault_code=_int()
    gen_power=_float()
    gen_power_fault_code=_int()
    batt_power=_float()
    batt_power_fault_code=_int()
    imp_power=_float()
    imp_power_fault_code=_int()
    allowed_export_power=_float()
    allowed_export_power_fault_code=_int()
    load_energy=_float()
    load_energy_fault_code=_int()
    gen_energy=_float()
    gen_energy_fault_code=_int()
    batt_imp_energy=_float()
    batt_imp_energy_fault_code=_int()
    batt_exp_energy=_float()
    batt_exp_energy_fault_code=_int()
    imp_energy=_float()
    imp_energy_fault_code=_int()
    exp_energy=_float()
    exp_energy_fault_code=_int()
    gen_batt_energy=_float()
    gen_batt_energy_fault_code=_int()
    gen_load_energy=_float()
    gen_load_energy_fault_code=_int()
    gen_grid_energy=_float()
    gen_grid_energy_fault_code=_int()
    batt_load_energy=_float()
    batt_load_energy_fault_code=_int()
    batt_grid_energy=_float()
    batt_grid_energy_fault_code=_int()
    grid_load_energy=_float()
    grid_load_energy_fault_code=_int()
    grid_batt_energy=_float()
    grid_batt_energy_fault_code=_int()
    allowed_export_energy=_float()
    allowed_export_energy_fault_code=_int()

    #ext batt drone (inverter / battery). multi inverter sites send EXT_BATT_*_2.._10, those go to extra
    ext_batt_status=_char(64)
    ext_batt_permissive=_int()
    ext_batt_permissive_data=_int()
    ext_batt_energy=_float()
    ext_batt_energy_fault_code=_int()
    ext_batt_current=_float()
    ext_batt_current_fault_code=_int()
    ext_batt_voltage=_float()
    ext_batt_voltage_fault_code=_int()
    ext_batt_dc_pwr=_float()
    ext_batt_dc_pwr_fault_code=_int()
    ext_batt_ac_pwr=_float()
    ext_batt_ac_pwr_fault_code=_int()
    ext_batt_ac_vars=_float()
    ext_batt_ac_vars_fault_code=_int()
    ext_batt_soc=_float()
    ext_batt_soc_fault_code=_int()
    ext_batt_soh=_float()
    ext_batt_soh_fault_code=_int()
    ext_batt_min_cell_voltage=_float()
    ext_batt_min_cell_voltage_fault_code=_int()
    ext_batt_max_cell_voltage=_float()
    ext_batt_max_cell_voltage_fault_code=_int()
    ext_batt_charge_rtg=_float()
    ext_batt_charge_rtg_fault_code=_int()
    ext_batt_discharge_rtg=_float()
    ext_batt_discharge_rtg_fault_code=_int()
    ext_batt_energy_rtg=_float()
    ext_batt_energy_rtg_fault_code=_int()
    ext_batt_grid_vac=_float()
    ext_batt_grid_vac_fault_code=_int()
    ext_batt_grid_vac_l1=_float()
    ext_batt_grid_vac_l1_fault_code=_int()
    ext_batt_grid_vac_l2=_float()
    ext_batt_grid_vac_l2_fault_code=_int()
    ext_batt_num_batt_modules=_float()
    ext_batt_num_batt_modules_fault_code=_int()
    ext_batt_nominal_frequency=_float()
    ext_batt_nominal_frequency_fault_code=_int()
    ext_batt_battery_type=_float()
    ext_batt_battery_type_fault_code=_int()
    ext_batt_inverter_mfr_code=_float()
    ext_batt_inverter_mfr_code_fault_code=_int()
    ext_batt_inverter_serial=_float()
    ext_batt_inverter_serial_fault_code=_int()
    ext_batt_inverter_fw_vers=_float()
    ext_batt_inverter_fw_vers_fault_code=_int()
    ext_batt_comlink_mfr_code=_float()
    ext_batt_comlink_mfr_code_fault_code=_int()
    ext_batt_comlink_serial=_float()
    ext_batt_comlink_serial_fault_code=_int()
    ext_batt_comlink_fw_vers=_float()
    ext_batt_comlink_fw_vers_fault_code=_int()

    #ext batt error details (only when the inverter reports them)
    ext_batt_grid_vac_l2l=_float()
    ext_batt_internal_vdc=_float()
    ext_batt_terminal_vdc=_float()
    ext_batt_battery_vdc=_float()
    ext_batt_cfet_code=_float()
    ext_batt_dfet_code=_float()
    ext_batt_service_mode=_int()
    ext_batt_service_data=_int()

    #MUC / cascade systems
    system_state=_char(64)
    system_permissive_data=_char(64)

    class Meta:
        db_table='gateway_poll'


class ExportEvent(GatewayDataBase): #EXPORT_EVENTS[]
    start_time=_datetime()
    export_power=_float()
    duration=_float()

    class Meta:
        db_table='export_event'


class ZigbeeDevice(GatewayDataBase): #ZB_DEVICES[]
    device_id=_char(32) #json key "ID"
    new=_bool()
    new_ts=_datetime()
    switch_state=_float()
    switch_state_ts=_datetime()
    energy_consumed=_float()
    energy_sum_ts=_datetime()
    power=_float()
    power_ts=_datetime()

    class Meta:
        db_table='zigbee_device'


class OperationStatus(GatewayDataBase): #OPERATION_STATUSES[]
    operation_type=_int() #0 = GRID_PROFILE, 1 = COMMISSIONING_PROFILE
    step=_int()
    status=_int()
    message=_text()
    data_request_uuid=_char(64) #DATA.REQUEST_UUID

    class Meta:
        db_table='operation_status'


class EastronMeterPhase(GatewayDataBase): #EASTRON_METERS_INFO.<EASTRON_MAINS|EASTRON_PV|EASTRON_ESS>.PHASE_n
    meter=_char(16) #MAINS, PV, ESS
    phase=_int()
    voltage=_float()
    current=_float()
    watt=_float()
    var=_float()
    pf=_float()
    phase_angle=_float()
    import_energy=_float()
    export_energy=_float()
    frequency=_float() #EASTRON_METERS_INFO.FREQUENCY

    class Meta:
        db_table='eastron_meter_phase'


# ---- battery errors -------------------------------------------------------

class BatteryErrorInfo(GatewayDataBase): #BATTERY_ERROR_INFO[] and NODES[].INVERTER_ERROR[]
    source=_char(32) #BATTERY_ERROR_INFO or INVERTER_ERROR
    node_id=_int() #MUC node, null for BATTERY_ERROR_INFO
    error_index=_int() #links to battery_error_fault_history / battery_error_lg_module rows of the same poll
    time=_datetime()
    type=_char(64) #CLEARED or battery type e.g. EGUANA_PT_3000C
    message=_text()
    inverter_state=_char(64)
    inverter_permissive=_int()
    inverter_permissive_data=_int()
    inverter_service_data=_int()
    inverter_firmware_version=_float()
    inverter_vdc=_float()
    inverter_internal_temperature=_float()
    inverter_soc=_float()
    grid_frequency=_float()
    grid_vac_l2l=_float()
    grid_vac_l1=_float()
    grid_vac_l2=_float()
    lg_rack_num_modules=_int()
    lg_rack_alarm_flags=_int()
    lg_rack_alarm_modules=_int()
    lg_rack_warning_flags=_int()
    lg_rack_warning_modules=_int()
    lg_rack_fault_flags=_int()
    lg_rack_fault_modules=_int()
    lg_rack_fault_1_flags=_int()
    lg_rack_fault_1_modules=_int()
    lg_rack_fault_2_flags=_int()
    lg_rack_fault_2_modules=_int()
    ace_rack_num_modules=_int() #other ACE_RACK_* keys go to extra
    us_5000_rack_alarm=_int()
    us_5000_rack_protection=_int()
    us_5000_request_flag=_int()

    class Meta:
        db_table='battery_error_info'


class BatteryErrorFaultHistory(GatewayDataBase): #BATTERY_ERROR_INFO[].FAULT_HISTORY[]
    error_index=_int()
    index=_int()
    fault_code=_int()
    permissive_code=_int()
    timestamp=_datetime() #epoch seconds in the json
    measurement_a=_float()
    measurement_b=_float()
    measurement_c=_float()
    measurement_d=_float()
    measurement_e=_float()

    class Meta:
        db_table='battery_error_fault_history'


class BatteryErrorLgModule(GatewayDataBase): #BATTERY_ERROR_INFO[].LG_MODULES[]
    error_index=_int()
    index=_int()
    hardware_version=_int()
    software_version=_int()
    status=_int()
    alarm_flags=_int()
    warning_flags=_int()
    fault_flags=_int()
    fault_1_flags=_int()
    fault_2_flags=_int()
    fault_2_flags_lo=_int()
    fault_2_flags_hi=_int()
    status_table=_int() #US_5000 "STATUS TABLE"
    flag_table=_int()
    error_table_lo=_int()
    error_table_hi=_int()

    class Meta:
        db_table='battery_error_lg_module'


# ---- battery modules ------------------------------------------------------

class BatteryModuleReading(GatewayDataBase): #BATTERY_MODULES.READINGS[]
    battery_type=_char(32) #BATTERY_MODULES.TYPE
    reading_index=_int()
    time=_datetime()
    serial_number=_text() #int on older firmware, list of 16 strings on newer (stored comma separated)
    discharge_energy=_float()
    sw_version=_int()
    hw_version=_int()
    vdc=_float()
    vdc_max=_float()
    vdc_min=_float()
    idc=_float()
    idc_max=_float()
    idc_min=_float()
    temp=_float()
    temp_max=_float()
    temp_min=_float()
    soc=_float()
    soh=_float()
    idc_charge_limit=_int()
    idc_discharge_limit=_int()
    status=_int()
    alarm_flags=_int()
    warning_flags=_int()
    fault_1_flags=_int()
    fault_2_flags=_int()
    fault_2_flags_lo=_int()
    fault_2_flags_hi=_int()
    #US_5000 / ACE keys (json keys have spaces), the rest of the ACE keys go to extra
    bms_temp=_float()
    nominal_capacity=_float()
    status_table=_int()
    error_table_lo=_int()
    error_table_hi=_int()
    cycle_count=_int()

    class Meta:
        db_table='battery_module_reading'


class BatteryDiagnostic(GatewayDataBase): #battery_diagnostic (pylontech)
    ext_batt_protecton=_int()
    ext_batt_protection_alarm=_bool()
    ext_batt_alarm_value=_int()
    ext_batt_alarm_alarm=_bool()
    ext_batt_mosfet_code=_int()
    ext_batt_mosfet_code_alarm=_bool()
    ext_batt_controlbits=_int()
    ext_batt_controlbits_alarm=_bool()
    ext_batt_alarmwarn_b2_b1=_int()
    ext_batt_alarmwarn_b2_b1_alarm=_bool()
    ext_batt_alarmwarn_b4_b3=_int()
    ext_batt_alarmwarn_b4_b3_alarm=_bool()
    ext_batt_num_modules_charge_protect=_int()
    ext_batt_num_modules_charge_protect_alarm=_bool()
    ext_batt_num_modules_discharge_protect=_int()
    ext_batt_num_modules_discharge_protect_alarm=_bool()
    ext_batt_max_cell_voltage_protect=_int()
    ext_batt_max_cell_voltage_protect_alarm=_bool()
    ext_batt_max_cell_voltage_threshold=_int()
    ext_batt_min_cell_voltage_protect=_int()
    ext_batt_min_cell_voltage_protect_alarm=_bool()
    ext_batt_min_cell_voltage_threshold=_int()
    ext_batt_cell_voltage_delta_alarm_threshold=_bool()
    ext_batt_cell_voltage_delta_threshold=_int()
    ext_batt_soc_delta=_int()
    ext_batt_soc_delta_threshold=_int()
    ext_batt_soc_delta_alarm=_bool()

    class Meta:
        db_table='battery_diagnostic'


class BatteryDiagnosticModule(GatewayDataBase): #battery_diagnostic.BATTERY_MODULES[]
    module_index=_int()
    ext_batt_min_cell_voltage_protect=_int()
    ext_batt_min_cell_voltage_protect_alarm=_bool()
    ext_batt_max_cell_voltage_protect=_int()
    ext_batt_max_cell_voltage_protect_alarm=_bool()
    ext_batt_status_table=_int()
    ext_batt_status_table_alarm=_bool()
    ext_batt_flag_table=_int()
    ext_batt_flag_table_alarm=_bool()
    ext_batt_cell_voltage_delta_alarm_threshold=_bool()
    ext_batt_cell_voltage_delta_threshold=_int()
    ext_batt_module_soc=_int()

    class Meta:
        db_table='battery_diagnostic_module'


# ---- OpenADR --------------------------------------------------------------

class OpenAdrEvent(GatewayDataBase): #OPENADR_EVENT_LOG[]
    event_index=_int() #links to openadr_stack_entry / openadr_log_data rows of the same poll
    active_index=_int()

    class Meta:
        db_table='openadr_event'


class OpenAdrStackEntry(GatewayDataBase): #OPENADR_EVENT_LOG[].OADR_STACK[]
    event_index=_int()
    index=_int()
    identifier=_char()
    modification=_int()
    start_time=_datetime() #epoch seconds in the json
    duration=_int()
    signal_name=_int()
    signal_type=_int()
    payload=_float()
    priority=_int()
    power_reserve=_int()
    disable_emergency_power_reserve=_int()
    oadr_battery_maintenance_disable_timeout=_int()

    class Meta:
        db_table='openadr_stack_entry'


class OpenAdrLogData(GatewayDataBase): #OPENADR_EVENT_LOG[].LOG_DATA[]
    event_index=_int()
    time=_datetime()
    status=_int()
    setpoint=_float()

    class Meta:
        db_table='openadr_log_data'


# ---- MUC / cascade nodes --------------------------------------------------

class MucNode(GatewayDataBase): #NODES[]
    node_id=_int()
    num_nodes=_int()
    harness_check_enabled=_int()
    ip_address=_char(64)
    mac_address=_char(64)
    serial_number=_char(64)
    inverter_type=_char(64)
    battery_type=_char(64)
    timestamp=_datetime()

    class Meta:
        db_table='muc_node'


class MucNodeError(GatewayDataBase): #NODES[].ERRORS[]
    node_id=_int()
    timestamp=_datetime()
    log_level=_int()
    message=_text()

    class Meta:
        db_table='muc_node_error'


class MucInverterData(GatewayDataBase): #NODES[].INVERTER_DATA (numeric / hex strings in the json are stored as numbers)
    node_id=_int()
    state=_char(64)
    permissive=_int()
    permissive_data=_int()
    active_fault_code=_int()
    inverter_manufacturer_code=_int()
    drm_status_bits=_int()
    charge_limit_type=_int()
    discharge_limit_type=_int()
    inverter_kwh_odometer=_int()
    grid_interactive_code=_int()
    battery_alarm=_int()
    battery_warning=_int()
    battery_fault=_int()
    aux_battery_fault=_int()
    battery_cfet_code=_float()
    battery_dfet_code=_float()
    node_indicator=_float()
    inverter_firmware_version=_float()
    inverter_serial_number=_float()
    comlink_firmware_version=_float()
    comlink_manufacturer_code=_float()
    comlink_serial_number=_float()
    battery_modules=_int()
    battery_data=_int()
    rated_power=_int()
    nominal_frequency=_int()
    vdc=_float()
    idc=_float()
    grid_frequency=_float()
    master_frequency=_float()
    output_vac=_float()
    grid_vac_line_to_line=_float()
    grid_vac_l1=_float()
    grid_vac_l2=_float()
    external_iac=_float()
    load_vac_line_to_line=_float()
    load_vac_l1=_float()
    load_vac_l2=_float()
    load_iac=_float()
    load_iac_l1=_float()
    load_iac_l2=_float()
    inverter_watts=_float()
    inverter_va=_float()
    inverter_var=_float()
    load_watts_line_to_line=_float()
    load_watts_l1=_float()
    load_watts_l2=_float()
    load_var_line_to_line=_float()
    load_var_l1=_float()
    load_var_l2=_float()
    grid_watts=_float()
    grid_var=_float()
    pv_watts=_float()
    iac_external_l2=_float()
    pen_vac=_float()
    power_factor=_float()
    idc_charge_max=_float()
    idc_discharge_max=_float()
    watt_charge_max=_float()
    watt_discharge_max=_float()
    iac_charge_max=_float()
    iac_discharge_max=_float()
    var_available_injection=_float()
    var_available_absorption=_float()
    demand=_float()
    internal_iac=_float()
    gfdi=_float()
    internal_temperature=_float()
    vdc_reference=_float()
    soc=_float()
    terminal_vdc=_float()
    rectifier_vdc=_float()
    battery_vdc=_float()
    battery_idc=_float()
    battery_max_cell_vdc=_float()
    battery_min_cell_vdc=_float()
    power_factor_lead_limit=_float()
    power_factor_lag_limit=_float()
    vdc_harness_detect=_float()
    vdc_ats_status=_float()
    available_watts_charging=_float()
    available_watts_discharging=_float()
    energy_rating=_float()
    energy=_float()
    dc_power=_float()
    min_reserve_soc=_float()
    max_reserve_soc=_float()
    offgrid_min_reserve_soc=_float()
    offgrid_max_reserve_soc=_float()

    class Meta:
        db_table='muc_inverter_data'


class MucBatteryData(GatewayDataBase): #NODES[].BATTERY_DATA, keys depend on battery type, uncommon ones go to extra
    node_id=_int()
    battery_type=_char(64) #NODES[].BATTERY_TYPE
    alarm_flags=_int()
    warning_flags=_int()
    fault_flags=_int()
    alarm_module=_int()
    warning_module=_int()
    fault_module=_int()
    vdc=_float()
    idc=_float()
    soc=_float()
    soh=_float()
    temperature=_float()
    min_cell_vdc=_float()
    min_cell_vdc_module=_int()
    max_cell_vdc=_float()
    max_cell_vdc_module=_int()
    min_cell_temperature=_float()
    min_cell_temperature_module=_int()
    max_cell_temperature=_float()
    max_cell_temperature_module=_int()
    vdc_charge_limit=_float()
    idc_charge_limit=_float()
    idc_discharge_limit=_float()
    num_modules=_int()

    class Meta:
        db_table='muc_battery_data'


class MucBatteryModule(GatewayDataBase): #NODES[].BATTERY_DATA.BATTERY_MODULES[], keys depend on battery type, uncommon ones go to extra
    node_id=_int()
    battery_type=_char(64)
    module_index=_int()
    status=_int()
    alarm_flags=_int()
    warning_flags=_int()
    fault_flags=_int()
    soc=_float()
    soh=_float()
    vdc=_float()
    idc=_float()
    min_vdc=_float()
    max_vdc=_float()
    average_vdc=_float()
    min_temperature=_float()
    max_temperature=_float()
    average_temperature=_float()
    idc_charge_limit=_float()
    idc_discharge_limit=_float()
    cycle_count=_int()
    hardware_version=_char(64)
    firmware_version=_char(64)
    serial_number_hi=_int()
    serial_number_lo=_int()

    class Meta:
        db_table='muc_battery_module'
