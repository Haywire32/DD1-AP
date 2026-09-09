"""Seed-bound, mode-aware 0.5.0 event handling."""
import hashlib
import re
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
    if m is None or m.tag == 'CAMPGC':
        raise ProtocolError('Event is outside the 12 campaign maps.')
    if mode == 'challenge':
        c = CHALLENGE_BY_TAG.get(mission_tag)
        if c is None or c.parent != m.tag:
            raise ProtocolError('Challenge identity does not match its map.')
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


def recover_victories(state, checked_locations):
    recovered = 0
    history = state.setdefault('victory_history', {})
    for address in checked_locations:
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
    else:
        complete = any(history.get(f'dd1.campaign.CAMPTS.victory.{d}')
            for d in DIFFICULTIES[settings.summit_goal_difficulty:])
    if complete and not state['goal_complete']:
        state['goal_complete'] = True
        recovered += 1
    return recovered
