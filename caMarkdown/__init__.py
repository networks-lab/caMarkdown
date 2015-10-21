from .parser import tokenizer

import os.path

def _reload():
    """This is for develop purposes only do not use otherwise.
    _reload() is not to be trusted"""
    import sys
    import importlib
    sys.modules['caMarkdown'] = importlib.reload(sys.modules['caMarkdown'])
    print("caMarkdown has been reloaded")

def test():
    loc = os.path.dirname(__file__) + "/tests"
    fileParse(loc + "/RecordTarget.md", loc + "/RecordMaster.md")
