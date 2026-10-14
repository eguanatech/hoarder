from django.shortcuts import render
from django.http import JsonResponse
import pandas as pd
import plotly.graph_objects as go
from .models import GatewayPoll

# ---------------------------------------------------------------------------
# Properties available for trending, grouped by category.
# Each entry is (field_name, display_label).
# ---------------------------------------------------------------------------
PROPERTY_GROUPS = {
    'Power': [
        ('freq',                 'Frequency (Hz)'),
        ('voltage',              'Voltage (V)'),
        ('vars',                 'Reactive Power (VAR)'),
        ('load_power',           'Load Power (W)'),
        ('gen_power',            'Generation Power (W)'),
        ('batt_power',           'Battery Power (W)'),
        ('imp_power',            'Import Power (W)'),
        ('allowed_export_power', 'Allowed Export Power (W)'),
    ],
    'Energy': [
        ('load_energy',          'Load Energy (Wh)'),
        ('gen_energy',           'Generation Energy (Wh)'),
        ('batt_imp_energy',      'Battery Import Energy (Wh)'),
        ('batt_exp_energy',      'Battery Export Energy (Wh)'),
        ('imp_energy',           'Import Energy (Wh)'),
        ('exp_energy',           'Export Energy (Wh)'),
        ('gen_batt_energy',      'Gen → Battery Energy (Wh)'),
        ('gen_load_energy',      'Gen → Load Energy (Wh)'),
        ('gen_grid_energy',      'Gen → Grid Energy (Wh)'),
        ('batt_load_energy',     'Battery → Load Energy (Wh)'),
        ('batt_grid_energy',     'Battery → Grid Energy (Wh)'),
        ('grid_load_energy',     'Grid → Load Energy (Wh)'),
        ('grid_batt_energy',     'Grid → Battery Energy (Wh)'),
        ('allowed_export_energy','Allowed Export Energy (Wh)'),
    ],
    'Battery': [
        ('ext_batt_energy',          'Battery Energy (Wh)'),
        ('ext_batt_current',         'Battery Current (A)'),
        ('ext_batt_voltage',         'Battery Voltage (V)'),
        ('ext_batt_dc_pwr',          'Battery DC Power (W)'),
        ('ext_batt_ac_pwr',          'Battery AC Power (W)'),
        ('ext_batt_soc',             'State of Charge (%)'),
        ('ext_batt_soh',             'State of Health (%)'),
        ('ext_batt_min_cell_voltage','Min Cell Voltage (V)'),
        ('ext_batt_max_cell_voltage','Max Cell Voltage (V)'),
        ('ext_batt_charge_rtg',      'Charge Rating (W)'),
        ('ext_batt_discharge_rtg',   'Discharge Rating (W)'),
    ],
    'Gateway Health': [
        ('gw_temp',      'Gateway Temperature (°C)'),
        ('gw_batt_level','Gateway Battery Level (%)'),
        ('gw_mem_use',   'Memory Use (%)'),
        ('gw_fs_use_1',  'Filesystem 1 Use (%)'),
        ('gw_fs_use_2',  'Filesystem 2 Use (%)'),
        ('gw_fs_use_3',  'Filesystem 3 Use (%)'),
        ('gw_fs_use_4',  'Filesystem 4 Use (%)'),
    ],
}

ALL_PROPERTIES = {field: label for group in PROPERTY_GROUPS.values() for field, label in group}
VALID_FIELDS = set(ALL_PROPERTIES)


def uid_autocomplete(request):
    """Return JSON list of gw_uid values matching the 'q' query parameter."""
    q = request.GET.get('q', '').strip()
    if not q:
        return JsonResponse([], safe=False)
    uids = (
        GatewayPoll.objects
        .filter(gw_uid__icontains=q)
        .values_list('gw_uid', flat=True)
        .distinct()
        .order_by('gw_uid')[:20]
    )
    return JsonResponse(list(uids), safe=False)


def trends(request):
    chart_div = None
    error = None
    selected_uid = ''
    selected_start = ''
    selected_end = ''
    selected_props = []

    if request.method == 'POST':
        selected_uid   = request.POST.get('uid', '').strip()
        selected_start = request.POST.get('start_date', '').strip()
        selected_end   = request.POST.get('end_date', '').strip()
        selected_props = [p for p in request.POST.getlist('properties') if p in VALID_FIELDS]

        if not selected_uid:
            error = 'Please enter an EMS UID.'
        elif not selected_props:
            error = 'Please select at least one property to plot.'
        else:
            qs = GatewayPoll.objects.filter(gw_uid=selected_uid).exclude(poll_timestamp=None)
            if selected_start:
                qs = qs.filter(poll_timestamp__date__gte=selected_start)
            if selected_end:
                qs = qs.filter(poll_timestamp__date__lte=selected_end)

            fields = ['poll_timestamp'] + selected_props
            qs = qs.order_by('poll_timestamp').values(*fields)

            df = pd.DataFrame.from_records(list(qs))

            if df.empty:
                error = f'No data found for UID "{selected_uid}" in the selected date range.'
            else:
                df['poll_timestamp'] = pd.to_datetime(df['poll_timestamp'], utc=True)

                fig = go.Figure()
                for field in selected_props:
                    if field in df.columns:
                        series = df[field].dropna()
                        if not series.empty:
                            fig.add_trace(go.Scatter(
                                x=df.loc[series.index, 'poll_timestamp'],
                                y=series,
                                mode='lines+markers',
                                name=ALL_PROPERTIES[field],
                            ))

                fig.update_layout(
                    title=f'EMS Trends — {selected_uid}',
                    xaxis_title='Timestamp (UTC)',
                    yaxis_title='Value',
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                    hovermode='x unified',
                    template='plotly_white',
                    height=550,
                )

                chart_div = fig.to_html(full_html=False, include_plotlyjs='cdn')

    context = {
        'property_groups': PROPERTY_GROUPS,
        'chart_div':       chart_div,
        'error':           error,
        'selected_uid':    selected_uid,
        'selected_start':  selected_start,
        'selected_end':    selected_end,
        'selected_props':  selected_props,
    }
    return render(request, 's3_ingestion/trends.html', context)
