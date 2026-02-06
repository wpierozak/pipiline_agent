import threading
import functools

def Monitor(cls):
    """
    Decorator that implements Monitor pattern for thread-safe object access.
    """
    original_init = cls.__init__

    @functools.wraps(original_init)
    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._lock = threading.Lock()

    cls.__init__ = new_init

    for name, attr in list(cls.__dict__.items()):
        if callable(attr) and not name.startswith("__"):
            original_method = attr 

            @functools.wraps(original_method)
            def wrapper(self, *args, method=original_method, **kwargs):
                with self._lock:
                    return method(self, *args, **kwargs)
            
            setattr(cls, name, wrapper)

    return cls

