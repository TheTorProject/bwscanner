
from Crypto.Util import number

from pylioness import Chacha20_Blake2b_Lioness


def to_pair_circuit_generator(relays, thispartition, partitions, key):
    n = len(relays)
    n_pairs = n*(n-1)/2
    for k in range(thispartition, n_pairs, partitions):
        (i, j) = to_pair(arbitrary_domain_perm(key, k, n_pairs), n)
        yield (relays[i], relays[j])

def arbitrary_domain_perm(key, x, n):
    block_cipher = Chacha20_Blake2b_Lioness(key, 40)
    block = number.long_to_bytes(x, blocksize=40)
    ciphertext = block_cipher.encrypt(block)
    return number.bytes_to_long(ciphertext) % n

def to_pair(x, n):
    """Pick the xth (0-based) pair out of the n*(n-1)/2 possible pairs."""

    #  0    <= x <  n-1  =>  i = 0
    #  n-1  <= x < 2n-3  =>  i = 1
    # 2n-3  <= x < 3n-6  =>  i = 2
    # 3n-6  <= x < 4n-10 =>  i = 3
    # 4n-10 <= x < 5n-15 =>  i = 4

    # k*n - k*(k+1)/2 <= x < (k+1)*n - (k+1)*(k+2)/2 => i = k
    lb = 0
    ub = n-1
    while True:
        i = (lb+ub) // 2
        too_high = (x < i*n - i*(i+1)/2)
        too_low = (x >= (i+1)*n - (i+1)*(i+2)/2)
        if too_low:
            lb = i+1
        elif too_high:
            ub = i-1
        else:
            # just right :-)
            break

    assert i*n - i*(i+1)/2 <= x
    assert x < (i+1)*n - (i+1)*(i+2)/2

    j = i+1 + x - (i*n - i*(i+1)/2)
    return (i, j)
