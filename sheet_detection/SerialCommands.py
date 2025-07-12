import configLib as cfg


MARK = 0xAA
F = cfg.config['NUM_OF_FINGERS']


def send_serial_data(commands, ser):
    ser.write(len(commands).to_bytes(4, 'big'))

    for pos, rotations, back_s, front_s, durations in commands:
        ser.write(int(pos).to_bytes(1, 'big'))
        for i in range(F):
            ser.write(int(rotations[i]).to_bytes(1, 'big', signed=True))
        for i in range(F):
            ser.write(int(back_s[i]).to_bytes(1, 'big'))
        for i in range(F):
            ser.write(int(front_s[i]).to_bytes(1, 'big'))
        for i in range(F):
            ser.write(int(durations[i]).to_bytes(4, 'big'))






