"""Applications that read the inventory and write beside it, never into it.

An application asks a question of the published inventory (what changes if a resource moves, what a
record conflict is worth) and answers it in its own products. It imports inventory factors and
records; it never writes a file the inventory builds, so the inventory reference is the same with
or without it (tests/test_gas_reallocation.py holds that).
"""
