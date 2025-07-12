from math import floor
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


def extract_notes_from_midi(file_path):
    mid = MidiFile(file_path)
    is_double_handed = False

    last_left_note = cfg.config['START_POS_LEFT_HAND']
    last_right_note = cfg.config['START_POS_RIGHT_HAND']

    start_tick_to_notes_right = defaultdict(list)
    start_tick_to_notes_left = defaultdict(list)
    active_notes = {}

    # Initialize tempo and ticks_per_beat from the MIDI file
    current_tempo = None  # We will extract this dynamically from the MIDI file
    ticks_per_beat = mid.ticks_per_beat  # Ticks per beat

    # Loop through MIDI tracks and messages
    for track in mid.tracks:
        # Accumulate time manually in ticks
        current_tick_time = 0
        for msg in track:
            current_tick_time += msg.time  # Accumulate time in ticks (delta-time)

            # Dynamically handle the tempo message we encounter
            if msg.type == 'set_tempo' and current_tempo != msg.tempo:
                current_tempo = msg.tempo  # Set tempo in microseconds per quarter note

            # Check if it's a 'note_on' message (with velocity > 0 meaning a note is pressed)
            if msg.type == 'note_on' and msg.velocity > 0:
                # Store the note start time in ticks
                active_notes[msg.note] = current_tick_time

            # Handle note off ('note_off' or 'note_on' with velocity == 0)
            elif (msg.type == 'note_off') or (msg.type == 'note_on' and msg.velocity == 0):
                if msg.note in active_notes:
                    # Calculate duration in ticks
                    start_tick_time = active_notes.pop(msg.note)
                    duration_ticks = current_tick_time - start_tick_time

                    # Ensure we have a tempo value before calculating
                    if current_tempo is not None:
                        # Convert duration from ticks to milliseconds using the current tempo
                        duration_milliseconds = ticks_to_milliseconds(duration_ticks, current_tempo, ticks_per_beat)

                        # Store note, positions and duration
                        note = msg.note % 12
                        note = midi_to_decimal_dict[note]
                        max_oct = cfg.config['NUM_OF_OCTAVES']
                        octave = min(msg.note // 12, max_oct) - 2  # -2 because that's the octave of note 0 in MIDI
                        note = note + octave * cfg.config['NUM_OF_WHITE_KEYS_IN_OCTAVE']
                        note = min(max(0, note), cfg.config['NUM_OF_WHITE_KEYS'])

                        dist_left = abs(note - last_left_note)
                        dist_right = abs(note - last_right_note)

                        if dist_left < dist_right:
                            start_tick_to_notes_left[start_tick_time].append(NoteWithPosition(note, duration_milliseconds))
                            last_left_note = note
                        else:
                            start_tick_to_notes_right[start_tick_time].append(NoteWithPosition(note, duration_milliseconds))
                            last_right_note = note

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
