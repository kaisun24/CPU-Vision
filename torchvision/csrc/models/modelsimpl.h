#ifndef MODELSIMPL_H
#define MODELSIMPL_H

#include <torch/torch.h>

namespace vision {
namespace models {
namespace modelsimpl {

// TODO here torch::relu_ and torch::adaptive_avg_pool2d wrapped in
// torch::nn::Fuctional don't work. so keeping these for now

inline torch::Tensor& relu_(torch::Tensor x) {
  return torch::relu_(x);
}

inline torch::Tensor relu6_(torch::Tensor x) {
  return torch::clamp_(x, 0, 6);
}

inline torch::Tensor adaptive_avg_pool2d(
    torch::Tensor x,
    torch::ExpandingArray<2> output_size) {
  return torch::adaptive_avg_pool2d(x, output_size);
}

inline torch::Tensor max_pool2d(
    torch::Tensor x,
    torch::ExpandingArray<2> kernel_size,
    torch::ExpandingArray<2> stride) {
  return torch::max_pool2d(x, kernel_size, stride);
}

} // namespace modelsimpl
} // namespace models
} // namespace vision

#endif // MODELSIMPL_H
