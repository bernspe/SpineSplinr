import pandas as pd

def getMLWorkflow(file):
    df = pd.read_excel(file)
    df.set_index('step', inplace=True)
    return df