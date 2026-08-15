# SPDX-License-Identifier: Apache-2.0
"""De-Scramble — probabilistic identity resolution into an Iceberg lakehouse.

The package is arranged as one module per stage of the pipeline, in the order
the data moves through them:

``config``      settings, resolved from defaults, environment and CLI flags
``sampledata``  synthetic record generator with deliberately injected duplicates
``reader``      generic CSV/Parquet input, read in batches with a watermark
``resolve``     Fellegi-Sunter record linkage, producing clusters of matches
``golden``      survivorship — one resolved record per cluster
``lakehouse``   Apache Iceberg output, local by default
``pipeline``    the composition of the above
"""

from descramble.config import PipelineConfig
from descramble.pipeline import PipelineResult, run_pipeline

__version__ = "0.1.0"

__all__ = ["PipelineConfig", "PipelineResult", "run_pipeline", "__version__"]
