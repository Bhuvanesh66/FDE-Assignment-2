"""FlashEats late-delivery KPI pipeline.

A small, explainable, dependable pipeline that takes the FlashEats client
sources (SQLite application database, CSV/JSON exports and the paginated
Dispatch API) through:

    ingest -> raw preservation -> profile -> validate -> clean/standardise
           -> business model -> metrics -> outputs -> validation gate

The package is organised by pipeline stage so that an evaluator can trace every
number in ``output/`` back to the stage and the rule that produced it.
"""

__version__ = "1.0.0"
