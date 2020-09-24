#ifndef REGISTER_H
#define REGISTER_H

#include "Video.h"

namespace {

static auto registerVideo =
    torch::class_<Video>("torchvision", "Video")
        .def(torch::init<std::string, std::string, bool>())
        .def("get_current_stream", &Video::getCurrentStream)
        .def("get_metadata", &Video::getStreamMetadata)
        .def("seek", &Video::Seek)
        .def("next", &Video::Next);

} // namespace
#endif
