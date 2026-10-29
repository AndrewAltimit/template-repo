"""Recurrent-depth signatures: tell looped language models from fixed-depth ones.

Companion toolkit to docs/hardware/recurrent-depth-signatures.md. Modules:

* :mod:`.config_inspect`, :mod:`.safetensors_io`, :mod:`.weights`,
  :mod:`.dynamics`: white-box analysis of open-weight checkpoints;
* :mod:`.graybox`: what log-probabilities and coarse budgets add;
* :mod:`.tasks`, :mod:`.client`, :mod:`.harness`, :mod:`.features`:
  black-box serial-depth and timing probes;
* :mod:`.scoring`, :mod:`.validation`: likelihood-ratio combination with an
  inconclusive outcome, and leave-one-out benchmarking on known models;
* :mod:`.simulate`: synthetic endpoints for offline tests.
"""

__version__ = "1.0.0"
