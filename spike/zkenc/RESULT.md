# zkenc spike, 2026-09-25T15:35Z

## 1. clone and build
Cloning into '/home/w51222tw/eth-tokyo/zkenc'...
commit: 2977641 docs: update js lib readme

Some errors have detailed explanations: E0277, E0308, E0599.
For more information about an error, try `rustc --explain E0277`.
error: could not compile `zkenc-core` (lib) due to 35 previous errors
warning: build failed, waiting for other jobs to finish...
cli: not built

## 2. compile the silence circuit
[32mWritten successfully:[0m ./silence.sym
[32mWritten successfully:[0m ./silence_js/silence.wasm
[32mEverything went okay[0m

## 3. witnesses

Node.js v18.19.1
true witness: generated
false witness: rejected by the circuit, as expected

## 5. conclusion
(write one paragraph: build status, encap status, decap status, key match yes/no, and the decision)
