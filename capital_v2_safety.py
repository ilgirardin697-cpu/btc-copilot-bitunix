"""CI only: remove exact reviewed integration; old protection logic stays frozen."""
FRAGMENTS=(
    'from guardian_capital_v2.host import before_guardian_cycle, owner_reply as capital_owner_reply\n',
    '            before_guardian_cycle(guardian)\n',
)
REPLACEMENT=('guardian.command_snapshot, capital_owner_reply(guardian),',
             'guardian.command_snapshot, guardian.telegram.send_owner,')


def normalize_capital(source):
    for fragment in FRAGMENTS:
        if source.count(fragment)!=1:raise AssertionError('Capital integration outside exact reviewed hook')
        source=source.replace(fragment,'',1)
    new,old=REPLACEMENT
    if source.count(new)!=1:raise AssertionError('Capital owner reply outside exact read-only wrapper')
    return source.replace(new,old,1)
