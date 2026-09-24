"""Dataset implementations for different backdoor types.

The concrete dataset builders now live in
``sleeper_agents.training.dataset_builder.DatasetBuilder``; the earlier
per-type dataset classes here were unused and broken (they referenced a
non-existent ``config.backdoor_response`` attribute), so they were removed.
"""

__all__: list[str] = []
