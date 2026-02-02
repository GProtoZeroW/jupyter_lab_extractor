# Source: tests/test_extract_magic.ipynb | Cell In[17] | 2026-02-01 21:14:39

from loguru import logger

def test_round_trip():
    """This test was both run by ipytest AND extracted to a file"""
    assert 1 + 1 == 2
    logger.debug("1 + 1 == 2")
    assert "hello".upper() == "HELLO"
    logger.debug("'hello'.upper() == 'HELLO'")
    logger.success("test_round_trip passed — cell was extracted and executed")

