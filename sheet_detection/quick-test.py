import bisect
import cv2
print([i for i in range(1, 6+1) for _ in range(2)])
l = [0, 2,5,6]
print(bisect.bisect_right(l, 5)-1)
print(f'l: {l[0:4]}')

k = {3:['f']}
k.setdefault(4, []).append('t')
k[3].append('ceva')
print(f'k: {k}')

p = 'ceva'
p += '#'
print('va' in p)

print((-1) % 5)

p = ([9,10,8], 'ceva')
print(p[0])

print([3] * 8)
print(35.0 % 1 == 0.0)

vre = [9]
if vre:
    print('ye')
else:
    print('no')





