"""Seed-bound, mode-aware 0.5.0 event handling."""
import hashlib
import re
try:
    from .dd1_campaign import enabled_maps, cd_goal_complete
    from .dd1_shop import SHOP_BASE, SHOP_COUNT, shop_count, completed_maps, purchase_available
except ImportError:
    from dd1_campaign import enabled_maps, cd_goal_complete
    from dd1_shop import SHOP_BASE, SHOP_COUNT, shop_count, completed_maps, purchase_available
from pathlib import Path
try:
    from .dd1_content import (ContentSettings, CHALLENGE_BY_TAG, CHECK_BY_ID,
                             matching_checks, DIFFICULTIES)
    from .dd1_protocol import (ProtocolError, MAP_BY_FILENAME, DIFFICULTY_INDEX,
        FINAL_WAVES, load_bridge_state, atomic_write_json, summit_is_unlocked)
except ImportError:
    from dd1_content import ContentSettings, CHALLENGE_BY_TAG, CHECK_BY_ID, matching_checks, DIFFICULTIES
    from dd1_protocol import (ProtocolError, MAP_BY_FILENAME, DIFFICULTY_INDEX,
        FINAL_WAVES, load_bridge_state, atomic_write_json, summit_is_unlocked)


def record_event(state, source, *, mode, map_name, mission_tag, difficulty, wave, victory):
    settings = ContentSettings.from_slot_data(state['content_settings'])
    m = MAP_BY_FILENAME.get(map_name.casefold())
    if m is None or m.tag not in {entry.tag for entry in enabled_maps(settings)}:
        raise ProtocolError('Event is outside this seed campaign.')
    if mode == 'challenge':
        c = CHALLENGE_BY_TAG.get(mission_tag)
        if c is None or c.parent != m.tag:
            raise ProtocolError('Challenge identity does not match its map.')
        # The seed-bound authoritative victory callback is the proof of clear.
        # Golden Tokens' Kismet wave counter differs across callback phases;
        # never discard a genuine victory solely for that offset.
        if victory and c.tag == 'SPECTS' and c.start <= wave <= c.final + 1:
            wave = c.final
        if victory and not c.victory_only and wave != c.final:
            raise ProtocolError('Challenge victory has an unexpected final wave; retain log for a map audit.')
    elif mission_tag != m.tag:
        raise ProtocolError('Mission identity does not match its map.')
    if mode == 'campaign' and victory and wave != FINAL_WAVES[m.tag]:
        raise ProtocolError('Campaign victory must be on the final wave.')
    try:
        checks = matching_checks(settings, mode=mode, map_tag=m.tag, difficulty=difficulty,
            wave=wave, victory=victory, challenge_tag=mission_tag if mode=='challenge' else '')
    except ValueError as error:
        raise ProtocolError(str(error)) from error
    if source in state['processed_files']:
        return False
    if victory and mode == 'campaign':
        d = ('easy', 'medium', 'hard', 'insane', 'nightmare', 'ruthless')[difficulty]
        state.setdefault('victory_history', {})[f'dd1.campaign.{m.tag}.victory.{d}'] = True
        if settings.completion_goal == 'summit' and m.tag == 'CAMPTS' and difficulty >= settings.summit_goal_difficulty:
            state['goal_complete'] = True
        if settings.completion_goal == 'crystalline_dimension' and cd_goal_complete(
                state['victory_history'], settings.crystalline_dimension_difficulty,
                settings.crystalline_dimension_unlock, state['received_items']):
            state['goal_complete'] = True
    if victory and mode == 'challenge':
        history = state.setdefault('challenge_victories', {})
        history[mission_tag] = max(history.get(mission_tag, -1), difficulty)
        if settings.completion_goal == 'challenges' and sum(
                d >= settings.challenge_goal_difficulty for tag, d in history.items()
                if tag in CHALLENGE_BY_TAG) >= settings.challenges_required:
            state['goal_complete'] = True
    for c in checks:
        key = f'dd1.v050.{c.address}'
        if key not in state['observed_locations']:
            state['observed_locations'][key] = {'prototype_location_id': c.address,
                'source_event': {'mode': mode, 'mission': mission_tag, 'difficulty': difficulty, 'wave': wave}}
            if c.address not in state['acknowledged_location_ids']:
                state['pending_location_ids'].append(c.address)
    state['pending_location_ids'] = sorted(set(state['pending_location_ids']))
    state['processed_files'].append(source)
    return True


def receive_live_event(line, state_path, expected_seed):
    if len(line) > 512:
        raise ProtocolError('DD1 event is too long.')
    try:
        fields = line.decode('ascii').rstrip('\r\n').split('|')
    except UnicodeDecodeError as error:
        raise ProtocolError('DD1 event must be ASCII.') from error
    if len(fields) != 8 or fields[0] != 'DD1EVENT2':
        raise ProtocolError('Expected a 0.5.0 mode-aware event.')
    _, identity, event, map_name, wave, difficulty, mode, tag = fields
    if identity != expected_seed or not re.fullmatch(r'dd1-[0-9a-f]{64}', identity):
        raise ProtocolError('Event belongs to a different seed; restart DD1.')
    if event == 'shop_purchase':
        if map_name != 'SHOP' or mode != 'shop' or tag != 'SHOP' or difficulty != 'easy' or not re.fullmatch(r'[0-9]{1,2}', wave):
            raise ProtocolError('Invalid shop event.')
        index = int(wave)
        if not 0 <= index < SHOP_COUNT:
            raise ProtocolError('Invalid shop index.')
        payload = '|'.join(fields[1:])
        state = load_bridge_state(state_path)
        settings = ContentSettings.from_slot_data(state['content_settings'])
        if not settings.shopsanity:
            raise ProtocolError('Shopsanity is disabled for this seed.')
        if index >= shop_count(settings):
            raise ProtocolError('This shop tier is not enabled for this seed.')
        bought = {n - SHOP_BASE for n in state['acknowledged_location_ids']}
        bought.update(v['prototype_location_id'] - SHOP_BASE for v in state['observed_locations'].values())
        fresh = index not in bought
        if fresh:
            if not purchase_available(index, completed_maps(state.get('victory_history', {})), bought):
                raise ProtocolError('Shop purchase is not yet available.')
            address = SHOP_BASE + index
            state['observed_locations'][f'dd1.v060.{address}'] = {
                'prototype_location_id': address, 'source_event': {'mode': 'shop', 'purchase': index}}
            state['pending_location_ids'] = sorted(set(state['pending_location_ids']) | {address})
            atomic_write_json(state_path, state)
        return ('DD1ACK2|' + payload + '\r\n').encode('ascii'), fresh
    if (event not in ('wave_complete', 'level_victory') or difficulty not in DIFFICULTY_INDEX
        or not re.fullmatch(r'[0-9]{1,2}', wave)
        or not re.fullmatch(r'[A-Za-z0-9_]{1,96}', map_name)):
        raise ProtocolError('Invalid DD1 event fields.')
    payload = '|'.join(fields[1:])
    source = 'tcp:' + hashlib.sha256(payload.encode('ascii')).hexdigest()
    state = load_bridge_state(state_path)
    fresh = record_event(state, source, mode=mode, map_name=map_name, mission_tag=tag,
                         difficulty=DIFFICULTY_INDEX[difficulty], wave=int(wave), victory=event=='level_victory')
    if fresh:
        atomic_write_json(state_path, state)
    return ('DD1ACK2|' + payload + '\r\n').encode('ascii'), fresh


def read_pending_event_journal(path: Path, expected_seed: str) -> list[str]:
    """Read retained game events without modifying the game's journal."""
    try:
        data = path.read_bytes()
        text = data.decode('utf-16') if data.startswith((b'\xff\xfe', b'\xfe\xff')) else data.decode('utf-8-sig', errors='replace')
    except (OSError, UnicodeError):
        return []
    section = ''
    events = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith((';', '#', '//')):
            continue
        if line.startswith('[') and line.endswith(']'):
            section = line[1:-1].strip().casefold()
            continue
        if section != 'dd1archipelago.apeventbridge' or '=' not in line:
            continue
        key, payload = line.split('=', 1)
        if key.strip().casefold() != 'pendingevents':
            continue
        payload = payload.strip()
        if payload.startswith('(') and payload.endswith(')'):
            payload = payload[1:-1].strip()
        if payload.startswith(expected_seed + '|') and payload not in events:
            events.append(payload)
    return events


def recover_victories(state, checked_locations):
    """Rebuild history only from victories that this DD1 client observed.

    A server location can also become checked through Archipelago's release or
    collect commands.  Such a check proves that its item was released, not that
    this player physically cleared the DD1 map.  The durable observed-location
    journal is therefore the trust boundary for victory recovery.
    """
    recovered = 0
    history = state.setdefault('victory_history', {})
    observed_addresses = {
        entry.get('prototype_location_id')
        for entry in state.get('observed_locations', {}).values()
        if isinstance(entry, dict) and type(entry.get('prototype_location_id')) is int
    }
    acknowledged_observations = observed_addresses.intersection(checked_locations)
    for address in acknowledged_observations:
        c = CHECK_BY_ID.get(address)
        if c is None or not c.victory:
            continue
        if c.mode == 'campaign':
            key = f'dd1.campaign.{c.map_tag}.victory.{DIFFICULTIES[c.difficulty]}'
            if key not in history:
                history[key] = True
                recovered += 1
        elif c.mode == 'challenge':
            challenges = state.setdefault('challenge_victories', {})
            if challenges.get(c.challenge_tag, -1) < c.difficulty:
                challenges[c.challenge_tag] = c.difficulty
                recovered += 1
    settings = ContentSettings.from_slot_data(state['content_settings'])
    if settings.completion_goal == 'challenges':
        complete = sum(d >= settings.challenge_goal_difficulty for tag, d in
            state.get('challenge_victories', {}).items() if tag in CHALLENGE_BY_TAG) >= settings.challenges_required
    elif settings.completion_goal == 'crystalline_dimension':
        complete = cd_goal_complete(history, settings.crystalline_dimension_difficulty,
                                   settings.crystalline_dimension_unlock, state['received_items'])
    else:
        complete = any(history.get(f'dd1.campaign.CAMPTS.victory.{d}')
            for d in DIFFICULTIES[settings.summit_goal_difficulty:])
    if complete and not state['goal_complete']:
        state['goal_complete'] = True
        recovered += 1
    return recovered
