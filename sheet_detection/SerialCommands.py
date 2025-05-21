def send_serial_data(commands, ser):
    ser.write(len(commands).to_bytes(4, byteorder='big'))
    for pos, rotations, back_s, front_s, durations in commands:
        ser.write(pos.to_bytes(1, byteorder='big', signed=False))
        for r in rotations:
            ser.write(r.to_bytes(1, byteorder='big', signed=True))
        for b in back_s:
            ser.write(b.to_bytes(1, byteorder='big', signed=False))
        for f in front_s:
            ser.write(f.to_bytes(1, byteorder='big', signed=False))
        for d in durations:
            ser.write(d.to_bytes(1, byteorder='big', signed=False))





