"""Financial reports.

Each report is a pure function over the company DB session plus a small
set of parameters (date range, basis). Routers shape the response; the
service returns structured data that also serializes cleanly to CSV.
"""
