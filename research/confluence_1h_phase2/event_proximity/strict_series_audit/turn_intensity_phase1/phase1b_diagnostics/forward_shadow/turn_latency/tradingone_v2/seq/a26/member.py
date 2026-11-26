"""Observe the member hypothesis without inventing its missing confirmations."""
def observe(context):
    h=context['1h'];v=h.get('bbwp');d=h.get('adx_slope');a=h.get('adx_acceleration')
    return dict(available_at=h['available_at'],adx_points_per_hour=d,adx_acceleration_points_per_hour2=a,
        bbwp_proxy=v,bbwp_proxy_gt50=None if v is None else v>50,
        ao_confirmation='UNSPECIFIED',koncorde_confirmation='UNSPECIFIED',
        directional_di=dict(plus=h.get('plus_di'),minus=h.get('minus_di')),
        closed_context={tf:dict(available_at=r['available_at'],ao=r.get('ao'),ao_slope=r.get('ao_slope'),
            adx=r.get('adx'),adx_slope=r.get('adx_slope'),pececillos=r.get('pececillos'),bbwp=r.get('bbwp'),structure=r.get('structure')) for tf,r in context.items()},
        refinement5m='DATA_NOT_CAPTURED',combination='NOT_EVALUABLE_WITHOUT_CONFIRMATION_DEFINITIONS',
        trade_authority='NONE')
