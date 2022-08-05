import math
from typing import Any, Callable, List, OrderedDict, Sequence, Tuple

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn, Tensor
from torchvision.ops.misc import Conv2dNormActivation, SqueezeExcitation
from torchvision.ops.stochastic_depth import StochasticDepth


def get_relative_position_index(height: int, width: int) -> torch.Tensor:
    coords = torch.stack(torch.meshgrid([torch.arange(height), torch.arange(width)]))
    coords_flat = torch.flatten(coords, 1)
    relative_coords = coords_flat[:, :, None] - coords_flat[:, None, :]
    relative_coords = relative_coords.permute(1, 2, 0).contiguous()
    relative_coords[:, :, 0] += height - 1
    relative_coords[:, :, 1] += width - 1
    relative_coords[:, :, 0] *= 2 * width - 1
    return relative_coords.sum(-1)


class GeluWrapper(nn.Module):
    """
    Gelu wrapper to make it compatible with `ConvNormActivation2D` which passed inplace=True
    to the activation function construction.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__()
        self._op = F.gelu

    def forward(self, x: Tensor) -> Tensor:
        return self._op(x)


class MBConv(nn.Module):
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        expansion_ratio: float,
        squeeze_ratio: float,
        stride: int,
        activation_fn: Callable[..., nn.Module],
        normalization_fn: Callable[..., nn.Module],
    ) -> None:
        super().__init__()

        proj: Sequence[nn.Module]
        self.proj: nn.Module

        should_proj = stride != 1 or in_channels != out_channels
        if should_proj:
            proj = [nn.Conv2d(in_channels, out_channels, kernel_size=1, stride=1, bias=False)]
            if stride == 2:
                proj = [nn.AvgPool2d(kernel_size=3, stride=stride, padding=1)] + proj  # type: ignore
            self.proj = nn.Sequential(*proj)
        else:
            self.proj = nn.Identity()  # type: ignore

        mid_channels = int(out_channels * expansion_ratio)
        sqz_channels = int(mid_channels * squeeze_ratio)

        _layers = OrderedDict()
        _layers["pre_norm"] = normalization_fn(in_channels)
        _layers["conv_a"] = Conv2dNormActivation(
            in_channels, mid_channels, 1, 1, 0, activation_layer=activation_fn, norm_layer=normalization_fn
        )
        _layers["conv_b"] = Conv2dNormActivation(
            mid_channels,
            mid_channels,
            3,
            stride,
            1,
            activation_layer=activation_fn,
            norm_layer=normalization_fn,
            groups=mid_channels,
        )
        _layers["squeeze_excitation"] = SqueezeExcitation(mid_channels, sqz_channels)
        _layers["conv_c"] = nn.Conv2d(in_channels=mid_channels, out_channels=out_channels, kernel_size=1, bias=False)

        self.layers = nn.Sequential(_layers)

    def forward(self, x: Tensor) -> Tensor:
        return self.layers(x) + self.proj(x)


class RelativePositionalMultiHeadAttention(nn.Module):
    def __init__(
        self,
        feat_dim: int,
        head_dim: int,
        max_seq_len: int,
    ) -> None:
        super().__init__()

        if feat_dim % head_dim != 0:
            raise ValueError(f"feat_dim: {feat_dim} must be divisible by head_dim: {head_dim}")

        self.n_heads = feat_dim // head_dim
        self.head_dim = head_dim
        self.size = int(math.sqrt(max_seq_len))
        self.max_seq_len = max_seq_len

        self.to_qkv = nn.Linear(feat_dim, self.n_heads * self.head_dim * 3)
        self.scale_factor = feat_dim**-0.5

        self.merge = nn.Linear(self.head_dim * self.n_heads, feat_dim)
        self.positional_bias = nn.parameter.Parameter(
            torch.zeros(((2 * self.size - 1) * (2 * self.size - 1), self.n_heads), dtype=torch.float32),
        )

        self.register_buffer("relative_position_index", get_relative_position_index(self.size, self.size))

        # initialize with truncated normal the bias
        self.positional_bias.data.normal_(mean=0, std=0.02)

    def _get_relative_positional_bias(self) -> torch.Tensor:
        bias_index = self.relative_position_index.view(-1)  # type: ignore
        relative_bias = self.positional_bias[bias_index].view(self.max_seq_len, self.max_seq_len, -1)  # type: ignore
        relative_bias = relative_bias.permute(2, 0, 1).contiguous()
        return relative_bias.unsqueeze(0)

    def forward(self, x: Tensor) -> Tensor:
        # X, Y and stand for X-axis group dim, Y-axis group dim
        B, G, P, D = x.shape
        H, DH = self.n_heads, self.head_dim

        qkv = self.to_qkv(x)
        q, k, v = torch.chunk(qkv, 3, dim=-1)

        q = q.reshape(B, G, P, H, DH).permute(0, 1, 3, 2, 4)
        k = k.reshape(B, G, P, H, DH).permute(0, 1, 3, 2, 4)
        v = v.reshape(B, G, P, H, DH).permute(0, 1, 3, 2, 4)

        k = k * self.scale_factor
        # X, Y and stand for X-axis group dim, Y-axis group dim
        dot_prod = torch.einsum("B G H I D, B G H J D -> B G H I J", q, k)
        pos_bias = self._get_relative_positional_bias()

        dot_prod = F.softmax(dot_prod + pos_bias, dim=-1)

        out = torch.einsum("B G H I J, B G H J D -> B G H I D", dot_prod, v)
        out = out.permute(0, 1, 3, 2, 4).reshape(B, G, P, D)

        out = self.merge(out)
        return out


class SwapAxes(nn.Module):
    def __init__(self, a: int, b: int) -> None:
        super().__init__()
        self.a = a
        self.b = b

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        res = torch.swapaxes(x, self.a, self.b)
        return res


class WindowPartition(nn.Module):
    """
    Function that takes in a tensor of shape [B, C, H, W] and partitions it
    in to a tensor of shape [B, H/P, W/P, P*P, C]
    """

    def __init__(self, partition_size: int) -> None:
        super().__init__()
        self.partition_size = partition_size

    def forward(self, x: Tensor) -> Tensor:
        B, C, H, W = x.shape
        P = self.partition_size
        # chunk up H and W dimensions
        x = x.reshape(B, C, H // P, P, W // P, P)
        x = x.permute(0, 2, 4, 3, 5, 1)
        # colapse P * P dimension
        x = x.reshape(B, (H // P) * (W // P), P * P, C)
        return x


class WindowDepartition(nn.Module):
    """
    Function that takes in a tensor of shape [B, H/P, W/P, P*P, C]
    and partitions it into a tensor of shape [B, C, H, W]
    """

    def __init__(self, partition_size: int, n_partitions: int) -> None:
        super().__init__()
        self.partition_size = partition_size
        self.n_partitions = n_partitions

    def forward(self, x: Tensor) -> Tensor:
        B, G, PP, C = x.shape
        P = self.partition_size
        HP, WP = self.n_partitions, self.n_partitions
        # split P * P dimension into 2 P tile dimensionsa
        x = x.reshape(B, HP, WP, P, P, C)
        # permute into B, C, HP, P, WP, P
        x = x.permute(0, 5, 1, 3, 2, 4)
        # reshape into B, C, H, W
        x = x.reshape(B, C, HP * P, WP * P)
        return x


class MLP(nn.Module):
    def __init__(
        self,
        in_dim: int,
        hidden_dim: int,
        activation_fn: Callable[..., nn.Module],
        normalization_fn: Callable[..., nn.Module],
        dropout: float,
    ) -> None:
        super().__init__()
        self.in_dim = in_dim
        self.hidden_dim = hidden_dim
        self.activation_fn = activation_fn
        self.normalization_fn = normalization_fn
        self.dropout = dropout

        self.layers = nn.Sequential(
            self.normalization_fn(in_dim),
            nn.Linear(in_dim, hidden_dim),
            self.activation_fn(),
            nn.Linear(hidden_dim, in_dim),
            nn.Dropout(dropout),
        )

    def forward(self, x: Tensor) -> Tensor:
        return x + self.layers(x)


class PartitionAttentionLayer(nn.Module):
    def __init__(
        self,
        in_channels: int,
        head_dim: int,
        # partitioning parameteres
        partition_size: int,
        partition_type: str,
        # grid size needs to be known at initialization time
        # because we need to know hamy relative offsets there are in the grid
        grid_size: Tuple[int, int],
        mlp_ratio: int,
        activation_fn: Callable[..., nn.Module],
        normalization_fn: Callable[..., nn.Module],
        attn_dropout: float,
        mlp_dropout: float,
    ) -> None:
        super().__init__()

        self.n_heads = in_channels // head_dim
        self.head_dim = head_dim
        self.n_partitions = grid_size[0] // partition_size
        self.partition_type = partition_type

        if partition_type not in ["grid", "window"]:
            raise ValueError("partition_type must be either 'grid' or 'window'")

        if partition_type == "window":
            p, g = partition_size, self.n_partitions
        else:
            p, g = self.n_partitions, partition_size

        partition_op = [WindowPartition(p)]
        departition_op = [WindowDepartition(p, g)]

        if partition_type == "grid":
            partition_op = partition_op + [SwapAxes(-2, -3)]  # type: ignore
            departition_op = [SwapAxes(-2, -3)] + departition_op  # type: ignore

        self.partition_op = nn.Sequential(*partition_op)
        self.departition_op = nn.Sequential(*departition_op)

        self.attn_layer = nn.Sequential(
            normalization_fn(in_channels),
            # it's always going to be partition_size ** 2 because
            # of the axis swap in the case of grid partitioning
            RelativePositionalMultiHeadAttention(in_channels, head_dim, partition_size**2),
            nn.Dropout(attn_dropout),
        )

        self.mlp_layer = MLP(in_channels, in_channels * mlp_ratio, activation_fn, normalization_fn, mlp_dropout)

        # layer scale factors
        self.attn_layer_scale = nn.parameter.Parameter(torch.ones(in_channels) * 1e-6)
        self.mlp_layer_scale = nn.parameter.Parameter(torch.ones(in_channels) * 1e-6)

    def forward(self, x: Tensor) -> Tensor:
        x = self.partition_op(x)
        x = self.attn_layer(x) * self.attn_layer_scale
        x = self.mlp_layer(x) * self.mlp_layer_scale
        x = self.departition_op(x)
        return x


class MaxVitLayer(nn.Module):
    def __init__(
        self,
        # conv parameters
        in_channels: int,
        out_channels: int,
        squeeze_ratio: float,
        expansion_ratio: float,
        stride: int,
        # conv + transformer parameters
        normalization_fn: Callable[..., nn.Module],
        activation_fn: Callable[..., nn.Module],
        # transformer parameters
        head_dim: int,
        mlp_ratio: int,
        mlp_dropout: float,
        attn_dropout: float,
        # partitioning parameters
        partition_size: int,
        grid_size: Tuple[int, int],
    ) -> None:
        super().__init__()

        layers: OrderedDict[str, Any] = OrderedDict()  # type: ignore

        # convolutional layer
        layers["MBconv"] = MBConv(
            in_channels=in_channels,
            out_channels=out_channels,
            expansion_ratio=expansion_ratio,
            squeeze_ratio=squeeze_ratio,
            stride=stride,
            activation_fn=activation_fn,
            normalization_fn=normalization_fn,
        )
        # attention layers, block -> grid
        layers["window_attention"] = PartitionAttentionLayer(
            in_channels=out_channels,
            head_dim=head_dim,
            partition_size=partition_size,
            partition_type="window",
            grid_size=grid_size,
            mlp_ratio=mlp_ratio,
            activation_fn=activation_fn,
            normalization_fn=nn.LayerNorm,
            attn_dropout=attn_dropout,
            mlp_dropout=mlp_dropout,
        )
        layers["grid_attention"] = PartitionAttentionLayer(
            in_channels=out_channels,
            head_dim=head_dim,
            partition_size=partition_size,
            partition_type="grid",
            grid_size=grid_size,
            mlp_ratio=mlp_ratio,
            activation_fn=activation_fn,
            normalization_fn=nn.LayerNorm,
            attn_dropout=attn_dropout,
            mlp_dropout=mlp_dropout,
        )
        self.layers = nn.Sequential(layers)

    def forward(self, x: Tensor) -> Tensor:
        return self.layers(x)


class MaxVitBlock(nn.Module):
    def __init__(
        self,
        # conv parameters
        in_channels: int,
        out_channels: int,
        squeeze_ratio: float,
        expansion_ratio: float,
        # conv + transformer parameters
        normalization_fn: Callable[..., nn.Module],
        activation_fn: Callable[..., nn.Module],
        # transformer parameters
        head_dim: int,
        mlp_ratio: int,
        mlp_dropout: float,
        attn_dropout: float,
        # partitioning parameters
        partition_size: int,
        input_grid_size: Tuple[int, int],
        # number of layers
        n_layers: int,
        p_stochastic: List[float],
    ) -> None:
        super().__init__()
        assert (
            len(p_stochastic) == n_layers
        ), f"p_stochastic must have length n_layers={n_layers}, got p_stochastic={p_stochastic}."

        self.layers = nn.ModuleList()
        # account for the first stride of the first layer
        self.grid_size = (input_grid_size[0] // 2, input_grid_size[1] // 2)

        for idx, p in enumerate(p_stochastic):
            stride = 2 if idx == 0 else 1
            self.layers += [
                MaxVitLayer(
                    in_channels=in_channels if idx == 0 else out_channels,
                    out_channels=out_channels,
                    squeeze_ratio=squeeze_ratio,
                    expansion_ratio=expansion_ratio,
                    stride=stride,
                    normalization_fn=normalization_fn,
                    activation_fn=activation_fn,
                    head_dim=head_dim,
                    mlp_ratio=mlp_ratio,
                    mlp_dropout=mlp_dropout,
                    attn_dropout=attn_dropout,
                    partition_size=partition_size,
                    grid_size=self.grid_size,
                ),
                StochasticDepth(p, mode="row"),
            ]

    def forward(self, x: Tensor) -> Tensor:
        for layer in self.layers:
            x = layer(x)
        return x


class MaxVit(nn.Module):
    def __init__(
        self,
        # stem and task parameters
        input_channels: int,
        stem_channels: int,
        input_size: Tuple[int, int],
        out_classes: int,
        # block parameters
        block_channels: List[int],
        block_layers: List[int],
        stochastic_depth_prob: float,
        # conv parameters
        squeeze_ratio: float,
        expansion_ratio: float,
        # conv + transformer parameters
        # normalization_fn is applied only to the conv layers
        # activation_fn is applied both to conv and transformer layers
        normalization_fn: Callable[..., nn.Module],
        activation_fn: Callable[..., nn.Module],
        # transformer parameters
        head_dim: int,
        mlp_ratio: int,
        mlp_dropout: float,
        attn_dropout: float,
        # partitioning parameters
        partition_size: int,
    ) -> None:
        super().__init__()

        # stem
        self.stem = nn.Sequential(
            Conv2dNormActivation(
                input_channels, stem_channels, 3, stride=2, norm_layer=None, activation_layer=None, bias=True
            ),
            Conv2dNormActivation(
                stem_channels, stem_channels, 3, stride=1, norm_layer=None, activation_layer=None, bias=True
            ),
        )

        # account for stem stride
        input_size = (input_size[0] // 2, input_size[1] // 2)

        # blocks
        self.blocks = nn.ModuleList()
        in_channels = [stem_channels] + block_channels[:-1]
        out_channels = block_channels

        # precompute the stochastich depth probabilities from 0 to stochastic_depth_prob
        # since we have N blocks with L layers, we will have N * L probabilities uniformly distributed
        # over the range [0, stochastic_depth_prob]
        p_stochastic = np.linspace(0, stochastic_depth_prob, num=sum(block_layers)).tolist()

        p_idx = 0
        for in_channel, out_channel, num_layers in zip(in_channels, out_channels, block_layers):
            self.blocks.append(
                MaxVitBlock(
                    in_channels=in_channel,
                    out_channels=out_channel,
                    squeeze_ratio=squeeze_ratio,
                    expansion_ratio=expansion_ratio,
                    normalization_fn=normalization_fn,
                    activation_fn=activation_fn,
                    head_dim=head_dim,
                    mlp_ratio=mlp_ratio,
                    mlp_dropout=mlp_dropout,
                    attn_dropout=attn_dropout,
                    partition_size=partition_size,
                    input_grid_size=input_size,
                    n_layers=num_layers,
                    p_stochastic=p_stochastic[p_idx : p_idx + num_layers],
                ),
            )
            input_size = self.blocks[-1].grid_size
            p_idx += num_layers

        self.classifier = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(block_channels[-1], out_classes, bias=False),
        )

    def forward(self, x: Tensor) -> Tensor:
        x = self.stem(x)
        for block in self.blocks:
            x = block(x)
        x = self.classifier(x)
        return x


def max_vit_T_224(num_classes: int) -> MaxVit:
    return MaxVit(
        input_channels=3,
        stem_channels=64,
        input_size=(224, 224),
        out_classes=num_classes,
        block_channels=[64, 128, 256, 512],
        block_layers=[2, 2, 5, 2],
        stochastic_depth_prob=0.2,
        squeeze_ratio=0.25,
        expansion_ratio=4.0,
        normalization_fn=nn.BatchNorm2d,
        activation_fn=GeluWrapper,
        head_dim=32,
        mlp_ratio=2,
        mlp_dropout=0.0,
        attn_dropout=0.0,
        partition_size=7,
    )


def max_vit_S_224(num_classes: int) -> MaxVit:
    return MaxVit(
        input_channels=3,
        stem_channels=64,
        input_size=(224, 224),
        out_classes=num_classes,
        block_channels=[96, 192, 384, 768],
        block_layers=[2, 2, 5, 2],
        stochastic_depth_prob=0.3,
        squeeze_ratio=0.25,
        expansion_ratio=4.0,
        normalization_fn=nn.BatchNorm2d,
        activation_fn=GeluWrapper,
        head_dim=32,
        mlp_ratio=2,
        mlp_dropout=0.0,
        attn_dropout=0.0,
        partition_size=7,
    )


def max_vit_B_224(num_classes: int) -> MaxVit:
    return MaxVit(
        input_channels=3,
        stem_channels=64,
        input_size=(224, 224),
        out_classes=num_classes,
        block_channels=[96, 192, 384, 768],
        block_layers=[2, 6, 14, 2],
        stochastic_depth_prob=0.4,
        squeeze_ratio=0.25,
        expansion_ratio=4.0,
        normalization_fn=nn.BatchNorm2d,
        activation_fn=GeluWrapper,
        head_dim=32,
        mlp_ratio=2,
        mlp_dropout=0.0,
        attn_dropout=0.0,
        partition_size=7,
    )


def max_vit_L_224(num_classes: int) -> MaxVit:
    return MaxVit(
        input_channels=3,
        stem_channels=128,
        input_size=(224, 224),
        out_classes=num_classes,
        block_channels=[128, 256, 512, 1024],
        block_layers=[2, 6, 14, 2],
        stochastic_depth_prob=0.6,
        squeeze_ratio=0.25,
        expansion_ratio=4.0,
        normalization_fn=nn.BatchNorm2d,
        activation_fn=GeluWrapper,
        head_dim=32,
        mlp_ratio=2,
        mlp_dropout=0.0,
        attn_dropout=0.0,
        partition_size=7,
    )
