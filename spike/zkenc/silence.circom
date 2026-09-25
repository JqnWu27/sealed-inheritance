pragma circom 2.1.6;

// The silence condition as a circuit: E - h - N = d with d a non-negative 8-bit number.
//   N  public   silence window in epochs
//   E  private  epoch of the finalized block
//   h  private  effective heartbeat epoch, max(heartbeat record, sealing epoch)
// Ten constraints. This is the same relation our KEM adapter encapsulates to.
template Silence(nbits) {
    signal input N;
    signal input E;
    signal input h;
    signal d;
    signal bits[nbits];

    d <== E - h - N;
    var acc = 0;
    for (var i = 0; i < nbits; i++) {
        bits[i] <-- (d >> i) & 1;
        bits[i] * (bits[i] - 1) === 0;
        acc += bits[i] * (1 << i);
    }
    acc === d;
}

component main {public [N]} = Silence(8);
