from .demo import DemoProvider
from .errors import ProviderError

def provider_for(mode):
    if mode == "live":
        from .live import LiveProvider
        return LiveProvider()
    return DemoProvider()
