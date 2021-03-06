from .parser import getTags, getParseTree
from .project import Project
from .tests.helpers import *
#from .dirHanders import makeProjectDir

version = '0.0.1'

def _reload():
    """This is for develop purposes only do not use otherwise. _reload() is not to be trusted as it is evil and will create zombies (also it sometimes doesn't work)."""
    import sys
    import importlib
    for i in range(3):
        for modName in sys.modules.keys():
            if "caMarkdown" == modName[:10]:
                sys.modules[modName] = importlib.reload(sys.modules[modName])
    print("caMarkdown has been reloaded, Zombies have risen")
