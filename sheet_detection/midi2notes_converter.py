import copy
from math import floor, ceil

import mido
from mido import MidiFile
import configLib as cfg
from sheet_detection.Notes import NoteWithPosition
from collections import defaultdict


# MIDI uses whole notes for every note (including tones), but for encoding piano keys,
#  the black keys have decimal part=0.5. Adjust to take that into account
midi_to_decimal_dict = {0: 1,
                        1: 1.5,
                        2: 2,
                        3: 2.5,
                        4: 3,
                        5: 4,
                        6: 4.5,
                        7: 5,
                        8: 5.5,
                        9: 6,
                        10: 6.5,
                        11: 7}


# Convert tempo from microseconds per quarter note to seconds per tick
def ticks_to_milliseconds(ticks, tempo, ticks_per_beat):
    """Convert ticks to milliseconds using the current tempo and ticks per beat (PPQ)."""
    return floor((ticks / ticks_per_beat) * (tempo / 1000) * cfg.config['MIDI_SPEED_FACTOR'])


def ticks_to_ms_with_tempos(start_tick, end_tick, tempos, ticks_per_beat):
    """
    tempos: list of (tick, tempo) sorted by tick.
    Returns real duration in milliseconds between start_tick and end_tick
    """
    total_ms = 0
    used_tempos = []
    for i, (tick_t, tempo) in enumerate(tempos):
        # End of this tempo region
        next_tick = tempos[i + 1][0] if i + 1 < len(tempos) else float('inf')

        # No overlap
        if end_tick <= tick_t:
            break
        if start_tick >= next_tick:
            continue

        # Compute overlap with this region
        region_start = max(start_tick, tick_t)
        region_end = min(end_tick, next_tick)
        tick_span = region_end - region_start

        used_tempos.append(mido.tempo2bpm(tempo))
        total_ms += (tick_span * tempo) / (ticks_per_beat * 1000)

    return ceil(total_ms)


def midi_note_to_key_pos(midi_note):
    # Compute position of piano key for note
    max_oct = cfg.config['NUM_OF_OCTAVES'] + 2
    octave = min(midi_note // 12, max_oct) - 2  # -2 because that's the octave of note 0 in MIDI
    note = midi_to_decimal_dict[midi_note % 12] + octave * cfg.config['NUM_OF_WHITE_KEYS_IN_OCTAVE']

    return min(max(0, note), cfg.config['NUM_OF_WHITE_KEYS'])


def extract_notes_from_midi(file_path):
    mid = MidiFile(file_path)
    ticks_per_beat = mid.ticks_per_beat  # Ticks per beat
    valid_track_index = -1  # For now, rely on separate tracks for each hand, only 2,
                            # but may exist tracks that have only metadata
    time_series = {}

    # Collect all tempo changes across tracks
    # Tempo is metadata, so it may appear in a track, but it applies for all tracks
    tempos = []
    for track in mid.tracks:
        tick_time = 0
        for msg in track:
            tick_time += msg.time
            if msg.type == 'set_tempo':
                tempos.append((tick_time, msg.tempo))
    tempos.sort(key=lambda x: x[0])

    if tempos is None:
        print('No tempos detected')
        return

    # Loop through MIDI tracks and messages
    for track in mid.tracks:
        # Accumulate time in ticks
        current_tick_time = 0

        if any(msg.type == 'note_on' for msg in track):
            valid_track_index += 1

        if valid_track_index > 1:
            break

        for msg in track:
            current_tick_time += msg.time  # Accumulate time in ticks (delta-time)
            hand = 'right' if valid_track_index == 0 else 'left'

            # Check if an event is happening
            if msg.type == 'note_on' or msg.type == 'note_off':
                current_time_ms = ticks_to_ms_with_tempos(0, current_tick_time, tempos,
                                                          ticks_per_beat)
                time_frame = time_series.setdefault(current_time_ms, {'left': {'active': [], 'inactive': []},
                                                                      'right': {'active': [], 'inactive': []}})[hand]
                # press_state = 1 if msg.velocity > 0 and msg.type == 'note_on' else 0
                state = 'active' if msg.velocity > 0 and msg.type == 'note_on' else 'inactive'
                note = midi_note_to_key_pos(msg.note)
                if note not in time_frame[state]:
                    time_frame[state].append(note)

    time_series = dict(sorted(time_series.items()))
    # for item in time_series.items():
    #     print(item)

    return time_series



