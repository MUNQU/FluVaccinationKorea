"""Data pipeline: download and process the Korean influenza data.

The scripts run as files (`python scripts/nhis.py`). This file only makes
`scripts.common` importable from the model package, so that the model and the
data use the same KDCA week rule.
"""
