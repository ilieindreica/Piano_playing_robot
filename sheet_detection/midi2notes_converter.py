import copy
from math import floor

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
    return floor((ticks / ticks_per_beat) * (tempo / 1000))


def ticks_to_ms_with_tempos(start_tick, end_tick, tempos, ticks_per_beat):
    """
    tempos: list of (tick, tempo) sorted by tick
    returns real duration in milliseconds between start_tick and end_tick
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

    return round(total_ms)


def extract_notes_from_midi(file_path):
    mid = MidiFile(file_path)

    ticks_per_beat = mid.ticks_per_beat  # Ticks per beat
    active_notes = {}
    valid_track_index = -1  # For now, rely on separate tracks for each hand, only 2,
                            # but may exist tracks that have only metadata
    time_series = {}
    is_double_handed = False

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
        end_of_previous = 0

        if any(msg.type == 'note_on' for msg in track):
            valid_track_index += 1

        if valid_track_index > 1:
            break

        for msg in track:
            current_tick_time += msg.time  # Accumulate time in ticks (delta-time)

            # Check if it's a 'note_on' message (with velocity > 0 meaning a note is pressed)
            if msg.type == 'note_on' and msg.velocity > 0:
                active_notes[msg.note] = current_tick_time

            # Handle note off ('note_off' or 'note_on' with velocity == 0)
            elif (msg.type == 'note_off') or (msg.type == 'note_on' and msg.velocity == 0):
                if msg.note in active_notes:
                    # Calculate duration in ticks
                    start_tick_time = active_notes.pop(msg.note)

                    # Convert duration from ticks to milliseconds using the current tempo
                    duration_milliseconds = ticks_to_ms_with_tempos(start_tick_time, current_tick_time, tempos,
                                                                    ticks_per_beat)

                    # Compute rest duration if needed
                    diff = start_tick_time - end_of_previous
                    rest_duration = (
                        # diff
                        ticks_to_ms_with_tempos(end_of_previous, start_tick_time, tempos, ticks_per_beat)
                        if diff > cfg.config['TIME_FOR_SOLENOID_RETRACTION']
                        else 0
                    )

                    # Compute position of piano key for note
                    max_oct = cfg.config['NUM_OF_OCTAVES'] + 2
                    octave = min(msg.note // 12, max_oct) - 2  # -2 because that's the octave of note 0 in MIDI
                    note = midi_to_decimal_dict[msg.note % 12] + octave * cfg.config['NUM_OF_WHITE_KEYS_IN_OCTAVE']
                    note = min(max(0, note), cfg.config['NUM_OF_WHITE_KEYS'])

                    hand = 'right' if valid_track_index == 0 else 'left' if valid_track_index == 1 else None

                    if hand is not None:
                        if rest_duration and not active_notes:
                            lst = time_series.setdefault(end_of_previous, {'left': [], 'right': []})[hand]
                            lst.append(NoteWithPosition('REST', rest_duration))

                        if duration_milliseconds:   # It may happen to exist notes with duration 0
                            lst = time_series.setdefault(start_tick_time, {'left': [], 'right': []})[hand]
                            note_obj = NoteWithPosition(note, duration_milliseconds)
                            if note_obj not in lst:
                                lst.append(note_obj)
                            end_of_previous = current_tick_time

    if valid_track_index >= 1:
        is_double_handed = True

    time_series = dict(sorted(time_series.items()))
    # for item in time_series.items():
    #     print(item)

    return time_series, is_double_handed



