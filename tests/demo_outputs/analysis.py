# Source: tests/demo_plots.ipynb | Cell In[4] | 2026-08-31 12:56:18
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def sine_wave(cycles=1, points=200):
    """x and sin(x) over `cycles` full periods."""
    x = np.linspace(0, cycles * 2 * np.pi, points)
    return x, np.sin(x)

# Source: tests/demo_plots.ipynb | Cell In[6] | 2026-08-31 12:56:18
def sine_table(cycles=1, points=5):
    """The same sine wave as a DataFrame."""
    x, y = sine_wave(cycles=cycles, points=points)
    return pd.DataFrame({"x": x, "sin_x": y})

