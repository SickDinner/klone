import unittest
from klone.cognition_local_model import inspect_local_model


class FakeTensor:
    def __init__(self, values):
        self.values = values
        self.shape = (len(values),)
    def detach(self):
        return self
    def reshape(self, *_):
        return self
    def numel(self):
        return len(self.values)
    def __getitem__(self, i):
        return self
    def item(self):
        return self.values.pop(0) if False else self.values[0]


class FakeHandle:
    def __init__(self, module): self.module = module
    def remove(self): self.module.hook = None


class FakeModule:
    def __init__(self): self.hook = None
    def register_forward_hook(self, hook):
        self.hook = hook
        return FakeHandle(self)


class FakeModel:
    def __init__(self): self.layer = FakeModule()
    def named_modules(self): return [("", self), ("layer", self.layer)]


class LocalModelTests(unittest.TestCase):
    def test_hooks_removed_on_success(self):
        model = FakeModel()
        def forward(): model.layer.hook(model.layer, (), FakeTensor([0.25]))
        result = inspect_local_model(model, forward)
        self.assertEqual(result["layer_count"], 1)
        self.assertIsNone(model.layer.hook)
        self.assertFalse(result["raw_activations_saved"])

    def test_hooks_removed_on_failure(self):
        model = FakeModel()
        def forward(): raise RuntimeError("inference failed")
        with self.assertRaises(RuntimeError):
            inspect_local_model(model, forward)
        self.assertIsNone(model.layer.hook)
