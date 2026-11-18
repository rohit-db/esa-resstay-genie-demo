import sys

import numpy
import pandas
import yaml


def test_local_environment_matches_serverless_environment_6():
    """Local tests must run on the same Python and packages as the serverless generator job."""
    assert sys.version_info[:2] == (3, 12)
    assert (numpy.__version__, pandas.__version__, yaml.__version__) == ("2.3.4", "2.3.3", "6.0.3")
