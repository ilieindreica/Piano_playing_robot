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

    notes_with_start_first = defaultdict(list)
    notes_with_start_second = defaultdict(list)

    # Collect all tempo changes across tracks
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
        tempo_index = 0
        end_of_previous = 0

        if any(msg.type == 'note_on' for msg in track):
            valid_track_index += 1

        if valid_track_index > 1:
            break

        for msg in track:
            current_tick_time += msg.time  # Accumulate time in ticks (delta-time)

            # Check if it's a 'note_on' message (with velocity > 0 meaning a note is pressed)
            if msg.type == 'note_on' and msg.velocity > 0:
                # Store the note start time in ticks
                active_notes[msg.note] = current_tick_time

            # Handle note off ('note_off' or 'note_on' with velocity == 0)
            elif (msg.type == 'note_off') or (msg.type == 'note_on' and msg.velocity == 0):
                if msg.note in active_notes:
                    # Calculate duration in ticks
                    start_tick_time = active_notes.pop(msg.note)

                    # Convert duration from ticks to milliseconds using the current tempo
                    duration_milliseconds = current_tick_time - start_tick_time #ticks_to_ms_with_tempos(start_tick_time, current_tick_time, tempos,
                                                                    # ticks_per_beat)

                    # Compute rest duration if needed
                    diff = start_tick_time - end_of_previous
                    rest_duration = (
                        diff
                        # ticks_to_ms_with_tempos(end_of_previous, start_tick_time, tempos, ticks_per_beat)
                        if diff > 0# cfg.config['TIME_FOR_SOLENOID_RETRACTION']
                        else 0
                    )

                    # Compute position of piano key for note
                    max_oct = cfg.config['NUM_OF_OCTAVES']
                    octave = min(msg.note // 12, max_oct) - 2  # -2 because that's the octave of note 0 in MIDI
                    note = midi_to_decimal_dict[msg.note % 12] + octave * cfg.config['NUM_OF_WHITE_KEYS_IN_OCTAVE']
                    note = min(max(0, note), cfg.config['NUM_OF_WHITE_KEYS'])

                    if valid_track_index == 0:
                        target_list = notes_with_start_first
                    elif valid_track_index == 1:
                        target_list = notes_with_start_second
                    else:
                        target_list = None

                    if target_list is not None:
                        if rest_duration:
                            target_list[end_of_previous].append(NoteWithPosition('REST', rest_duration))
                        target_list[start_tick_time].append(NoteWithPosition(note, duration_milliseconds))

                    end_of_previous = current_tick_time

    notes_with_start_first = defaultdict(list, dict(sorted(notes_with_start_first.items())))
    notes_with_start_second = defaultdict(list, dict(sorted(notes_with_start_second.items())))

    notes1 = list(notes_with_start_first.values())
    notes2 = list(notes_with_start_second.values())
    k1 = list(notes_with_start_first.keys())
    k2 = list(notes_with_start_second.keys())
    d1 = notes1[0][0].duration
    d2 = notes2[0][0].duration
    i = j = 1
    while i < len(notes1) or j < len(notes2):
        if abs(d1 - d2) <= 0 and (i < len(notes1) and j < len(notes2)):
            print("####", k1[i], k2[j], "  ", (d1, d2))
            d1 = notes1[i][0].duration
            d2 = notes2[j][0].duration
            i += 1
            j += 1
        elif j == len(notes2) or (i < len(notes1) and d1 < d2):
            print(f'1 {k1[i]} {d1, d2}')
            d2 -= d1
            d1 = notes1[i][0].duration
            i += 1
        elif i == len(notes1) or (j < len(notes2) and d2 < d1):
            print(f'2 {k2[j]} {d1, d2}')
            d1 -= d2
            d2 = notes2[j][0].duration
            j += 1

    print('FINISHED')

    return notes_with_start_first, notes_with_start_second


def extract_notes_from_midi2(file_path):
    is_double_handed = False

    last_left_note = cfg.config['START_POS_LEFT_HAND']
    last_right_note = cfg.config['START_POS_RIGHT_HAND']


    sorted_starts_right = sorted(start_tick_to_notes_right.keys())
    sorted_starts_left = sorted(start_tick_to_notes_left.keys())
    prev_end_tick = 0
    note_data_right = []
    note_data_left = []

    # max_len = max(len(sorted_starts_left), len(sorted_starts_right))
    # for i in range(max_len):
    #     com1 = sorted_starts_left[i] if i < len(sorted_starts_left) else None
    #     com2 = sorted_starts_right[i] if i < len(sorted_starts_right) else None
    #     print(f'{com1}      {com2}')

    # Handle RIGHT hand notes
    for start_tick in sorted_starts_right:
        notes_with_pos_at_t = start_tick_to_notes_right[start_tick]
        min_duration = min([note.duration for note in notes_with_pos_at_t])

        # Check for rest
        if start_tick > prev_end_tick:
            rest_duration_ticks = start_tick - prev_end_tick
            rest_duration_ms = ticks_to_milliseconds(rest_duration_ticks, current_tempo, ticks_per_beat)
            note_data_right.append([NoteWithPosition('REST', rest_duration_ms)])

        note_data_right.append(notes_with_pos_at_t)

        prev_end_tick = start_tick + int(min_duration * ticks_per_beat * 1000 / current_tempo)

    prev_end_tick = 0
    # Handle LEFT hand notes
    for start_tick in sorted_starts_left:
        notes_with_pos_at_t = start_tick_to_notes_left[start_tick]
        min_duration = min([note.duration for note in notes_with_pos_at_t])

        # Check for rest
        if start_tick > prev_end_tick:
            rest_duration_ticks = start_tick - prev_end_tick
            rest_duration_ms = ticks_to_milliseconds(rest_duration_ticks, current_tempo, ticks_per_beat)
            note_data_left.append([NoteWithPosition('REST', rest_duration_ms)])

        note_data_left.append(notes_with_pos_at_t)
        prev_end_tick = start_tick + int(min_duration * ticks_per_beat * 1000 / current_tempo)

    time_series = [note_data_right, note_data_left]
    if note_data_left:
        is_double_handed = True

    return time_series, is_double_handed
