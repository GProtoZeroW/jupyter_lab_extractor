# Source: tests/test_extract_magic.ipynb | Cell In[18] | 2026-11-01 08:20:41

import logging
logger = logging.getLogger("test_extract_magic")

def test_round_trip():
    """This test was both run by ipytest AND extracted to a file"""
    assert 1 + 1 == 2
    logger.debug("1 + 1 == 2")
    assert "hello".upper() == "HELLO"
    logger.debug("'hello'.upper() == 'HELLO'")
    logger.success("test_round_trip passed — cell was extracted and executed")

