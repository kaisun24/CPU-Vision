from functools import partial
from itertools import chain
import random

import torch
from torchvision import models
import torchvision
from torchvision.models.detection.backbone_utils import resnet_fpn_backbone
from torchvision.models.feature_extraction import create_feature_extractor
from torchvision.models.feature_extraction import get_graph_node_names
from torchvision.models._utils import IntermediateLayerGetter

import pytest

from common_utils import set_rng_seed


# Suppress diff warning from create_feature_extractor
create_feature_extractor = partial(
    create_feature_extractor, suppress_diff_warning=True)
get_graph_node_names = partial(
    get_graph_node_names, suppress_diff_warning=True)


def get_available_models():
    # TODO add a registration mechanism to torchvision.models
    return [k for k, v in models.__dict__.items()
            if callable(v) and k[0].lower() == k[0] and k[0] != "_"]


@pytest.mark.parametrize('backbone_name', ('resnet18', 'resnet50'))
def test_resnet_fpn_backbone(backbone_name):
    x = torch.rand(1, 3, 300, 300, dtype=torch.float32, device='cpu')
    y = resnet_fpn_backbone(backbone_name=backbone_name, pretrained=False)(x)
    assert list(y.keys()) == ['0', '1', '2', '3', 'pool']


# Needed by TestFxFeatureExtraction.test_leaf_module_and_function
def leaf_function(x):
    return int(x)


class TestFxFeatureExtraction:
    inp = torch.rand(1, 3, 224, 224, dtype=torch.float32, device='cpu')
    model_defaults = {
        'num_classes': 1,
        'pretrained': False
    }
    leaf_modules = [torchvision.ops.StochasticDepth]

    def _create_feature_extractor(self, *args, **kwargs):
        """
        Apply leaf modules
        """
        return create_feature_extractor(
            *args, **kwargs,
            tracer_kwargs={'leaf_modules': self.leaf_modules},
            suppress_diff_warning=True)

    def _get_return_nodes(self, model):
        set_rng_seed(0)
        exclude_nodes_filter = ['getitem', 'floordiv', 'size', 'chunk']
        train_nodes, eval_nodes = get_graph_node_names(
            model, tracer_kwargs={'leaf_modules': self.leaf_modules})
        # Get rid of any nodes that don't return tensors as they cause issues
        # when testing backward pass.
        train_nodes = [n for n in train_nodes
                       if not any(x in n for x in exclude_nodes_filter)]
        eval_nodes = [n for n in eval_nodes
                      if not any(x in n for x in exclude_nodes_filter)]
        return random.sample(train_nodes, 10), random.sample(eval_nodes, 10)

    @pytest.mark.parametrize('model_name', get_available_models())
    def test_build_fx_feature_extractor(self, model_name):
        set_rng_seed(0)
        model = models.__dict__[model_name](**self.model_defaults).eval()
        train_return_nodes, eval_return_nodes = self._get_return_nodes(model)
        # Check that it works with both a list and dict for return nodes
        self._create_feature_extractor(
            model, train_return_nodes={v: v for v in train_return_nodes},
            eval_return_nodes=eval_return_nodes)
        self._create_feature_extractor(
            model, train_return_nodes=train_return_nodes,
            eval_return_nodes=eval_return_nodes)
        # Check must specify return nodes
        with pytest.raises(AssertionError):
            self._create_feature_extractor(model)
        # Check return_nodes and train_return_nodes / eval_return nodes
        # mutual exclusivity
        with pytest.raises(AssertionError):
            self._create_feature_extractor(
                model, return_nodes=train_return_nodes,
                train_return_nodes=train_return_nodes)
        # Check train_return_nodes / eval_return nodes must both be specified
        with pytest.raises(AssertionError):
            self._create_feature_extractor(
                model, train_return_nodes=train_return_nodes)
        # Check invalid node name raises ValueError
        with pytest.raises(ValueError):
            # First just double check that this node really doesn't exist
            if not any(n.startswith('l') or n.startswith('l.') for n
                       in chain(train_return_nodes, eval_return_nodes)):
                self._create_feature_extractor(
                    model, train_return_nodes=['l'], eval_return_nodes=['l'])
            else:  # otherwise skip this check
                raise ValueError

    @pytest.mark.parametrize('model_name', get_available_models())
    def test_forward_backward(self, model_name):
        model = models.__dict__[model_name](**self.model_defaults).train()
        train_return_nodes, eval_return_nodes = self._get_return_nodes(model)
        model = self._create_feature_extractor(
            model, train_return_nodes=train_return_nodes,
            eval_return_nodes=eval_return_nodes)
        out = model(self.inp)
        sum([o.mean() for o in out.values()]).backward()

    def test_feature_extraction_methods_equivalence(self):
        model = models.resnet18(**self.model_defaults).eval()
        return_layers = {
            'layer1': 'layer1',
            'layer2': 'layer2',
            'layer3': 'layer3',
            'layer4': 'layer4'
        }

        ilg_model = IntermediateLayerGetter(
            model, return_layers).eval()
        fx_model = self._create_feature_extractor(model, return_layers)

        # Check that we have same parameters
        for (n1, p1), (n2, p2) in zip(ilg_model.named_parameters(),
                                      fx_model.named_parameters()):
            assert n1 == n2
            assert p1.equal(p2)

        # And that ouputs match
        with torch.no_grad():
            ilg_out = ilg_model(self.inp)
            fgn_out = fx_model(self.inp)
        assert all(k1 == k2 for k1, k2 in zip(ilg_out.keys(), fgn_out.keys()))
        for k in ilg_out.keys():
            assert ilg_out[k].equal(fgn_out[k])

    @pytest.mark.parametrize('model_name', get_available_models())
    def test_jit_forward_backward(self, model_name):
        set_rng_seed(0)
        model = models.__dict__[model_name](**self.model_defaults).train()
        train_return_nodes, eval_return_nodes = self._get_return_nodes(model)
        model = self._create_feature_extractor(
            model, train_return_nodes=train_return_nodes,
            eval_return_nodes=eval_return_nodes)
        model = torch.jit.script(model)
        fgn_out = model(self.inp)
        sum([o.mean() for o in fgn_out.values()]).backward()

    def test_train_eval(self):
        class TestModel(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.dropout = torch.nn.Dropout(p=1.)

            def forward(self, x):
                x = x.mean()
                x = self.dropout(x)  # dropout
                if self.training:
                    x += 100  # add
                else:
                    x *= 0  # mul
                x -= 0  # sub
                return x

        model = TestModel()

        train_return_nodes = ['dropout', 'add', 'sub']
        eval_return_nodes = ['dropout', 'mul', 'sub']

        def checks(model, mode):
            with torch.no_grad():
                out = model(torch.ones(10, 10))
            if mode == 'train':
                # Check that dropout is respected
                assert out['dropout'].item() == 0
                # Check that control flow dependent on training_mode is respected
                assert out['sub'].item() == 100
                assert 'add' in out
                assert 'mul' not in out
            elif mode == 'eval':
                # Check that dropout is respected
                assert out['dropout'].item() == 1
                # Check that control flow dependent on training_mode is respected
                assert out['sub'].item() == 0
                assert 'mul' in out
                assert 'add' not in out

        # Starting from train mode
        model.train()
        fx_model = self._create_feature_extractor(
            model, train_return_nodes=train_return_nodes,
            eval_return_nodes=eval_return_nodes)
        # Check that the models stay in their original training state
        assert model.training
        assert fx_model.training
        # Check outputs
        checks(fx_model, 'train')
        # Check outputs after switching to eval mode
        fx_model.eval()
        checks(fx_model, 'eval')

        # Starting from eval mode
        model.eval()
        fx_model = self._create_feature_extractor(
            model, train_return_nodes=train_return_nodes,
            eval_return_nodes=eval_return_nodes)
        # Check that the models stay in their original training state
        assert not model.training
        assert not fx_model.training
        # Check outputs
        checks(fx_model, 'eval')
        # Check outputs after switching to train mode
        fx_model.train()
        checks(fx_model, 'train')

    def test_leaf_module_and_function(self):
        class LeafModule(torch.nn.Module):
            def forward(self, x):
                # This would raise a TypeError if it were not in a leaf module
                int(x.shape[0])
                return torch.nn.functional.relu(x + 4)

        class TestModule(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.conv = torch.nn.Conv2d(3, 1, 3)
                self.leaf_module = LeafModule()

            def forward(self, x):
                leaf_function(x.shape[0])
                x = self.conv(x)
                return self.leaf_module(x)

        model = self._create_feature_extractor(
            TestModule(), return_nodes=['leaf_module'],
            tracer_kwargs={'leaf_modules': [LeafModule],
                           'autowrap_functions': [leaf_function]}).train()

        # Check that LeafModule is not in the list of nodes
        assert 'relu' not in [str(n) for n in model.graph.nodes]
        assert 'leaf_module' in [str(n) for n in model.graph.nodes]

        # Check forward
        out = model(self.inp)
        # And backward
        out['leaf_module'].mean().backward()
