# -*- coding: utf-8 -*-
"""
Freeze pytest.main() with tomial_clicky_tooth included.
"""
import sys
import tomial_clicky_tooth

import pytest

sys.exit(pytest.main(sys.argv[1:] + ["--no-cov", "--tb=native"]))
