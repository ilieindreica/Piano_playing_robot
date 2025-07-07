class NoteOrRest:
    def __init__(self, pitch=None, duration=0.0):
        # Use a list for pitch so that chords (multiple pitches) can be stored
        self.pitch = pitch if pitch is not None else []
        self.duration = duration

    def __repr__(self):
        return f"(pitch={self.pitch}, duration={self.duration})"


# Same as NoteOrRest, but has 'pos' instead of 'pitch', to be more intuitive in the context where the concept of
# position is used instead of the concept of pitch
class NoteWithPosition:
    def __init__(self, position=None, duration=0.0):
        # Use a list for position so that chords (multiple pitches) can be stored
        self.pos = position if position is not None else []
        self.duration = duration

    def __repr__(self):
        return f"NoteWithPosition(position={self.pos}, duration={self.duration})"
