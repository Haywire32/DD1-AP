"""Receipt-time, seed-bound Bank Mana awards. Never rescale an old receipt."""
import hashlib
import random

try:
    from .dd1_ap_adapter import ingest_received_packet
    from .dd1_content import MANA_REWARDS, SCALED_MANA_ITEM
    from .dd1_protocol import ProtocolError
    from .dd1_shop import completed_maps
except ImportError:  # Direct bridge development/testing.
    from dd1_ap_adapter import ingest_received_packet
    from dd1_content import MANA_REWARDS, SCALED_MANA_ITEM
    from dd1_protocol import ProtocolError
    from dd1_shop import completed_maps

MANA_BANDS = ((25_000, 50_000, 75_000), (250_000, 500_000, 1_000_000),
              (5_000_000, 10_000_000, 20_000_000), (50_000_000, 100_000_000, 500_000_000))


def mana_band(clears):
    return 0 if clears < 8 else 1 if clears < 12 else 2 if clears < 16 else 3


def validate_mana_ledger(state):
    ledger = state.get('mana_payouts', {})
    if not isinstance(ledger, dict):
        raise ProtocolError('Invalid saved Bank Mana payouts.')
    receipts = {str(r['index']) for r in state['received_items']}
    for key, payout in ledger.items():
        if key not in receipts or not isinstance(payout, dict) or set(payout) != {'maps', 'amount'}:
            raise ProtocolError('Invalid saved Bank Mana receipt.')
        if (type(payout['maps']) is not int or payout['maps'] < 0
                or type(payout['amount']) is not int
                or payout['amount'] not in MANA_BANDS[mana_band(payout['maps'])]):
            raise ProtocolError('Invalid saved Bank Mana amount.')


def mana_reward_units(state, item_ids):
    """Existing game wire uses cumulative 25k units, not an overflowing mana sum."""
    validate_mana_ledger(state)
    ledger = state.get('mana_payouts', {})
    scaling_id = item_ids[SCALED_MANA_ITEM]
    indices = {str(r['index']) for r in state['received_items'] if r['item_id'] == scaling_id}
    if set(ledger) != indices:
        # Missing awards cannot safely be reconstructed from current progress.
        raise ProtocolError('Saved Bank Mana payouts do not match the item history; restore the client state backup.')
    fixed = {item_ids[name]: amount // 25_000 for name, amount in MANA_REWARDS.items()}
    units = sum(fixed.get(r['item_id'], 0) for r in state['received_items'])
    units += sum(p['amount'] // 25_000 for p in ledger.values())
    if units > 1_000_000_000:
        raise ProtocolError('Bank Mana history exceeds the supported reward counter.')
    return units


def ingest_mana_packet(state, packet, item_ids, seed_identity):
    """Call before the single atomic receipt-state write; no I/O or game grants."""
    mana_reward_units(state, item_ids)
    previous_index = state['last_received_index']
    added = ingest_received_packet(state, packet)
    new_mana = [r for r in state['received_items']
                if r['index'] > previous_index and r['item_id'] == item_ids[SCALED_MANA_ITEM]]
    if not new_mana:
        return added
    clears = (completed_maps(state.get('victory_history', {}))
              if state.get('content_settings', {}).get('completion_goal') == 'crystalline_dimension' else 0)
    band = mana_band(clears)
    ledger = state.setdefault('mana_payouts', {})
    ordinal = sum(mana_band(p['maps']) == band for p in ledger.values())
    for receipt in new_mana:
        # Independent bags per payout band, shared across packets and reconnects.
        # Each full bag has exactly one of each value, with a seed-specific order.
        entropy = hashlib.sha256(f'{seed_identity}|bank-mana|{band}|{ordinal // 3}'.encode()).digest()
        bag = list(MANA_BANDS[band])
        random.Random(entropy).shuffle(bag)
        ledger[str(receipt['index'])] = {'maps': clears, 'amount': bag[ordinal % 3]}
        ordinal += 1
    mana_reward_units(state, item_ids)
    return added
