from spot.cameras import prefer_visual_source, visual_sources


def test_depth_sources_are_hidden():
    sources = [
        "back_depth",
        "back_depth_in_visual_frame",
        "back_fisheye_image",
        "frontleft_fisheye_image",
        "left_depth",
    ]
    assert visual_sources(sources) == ["back_fisheye_image", "frontleft_fisheye_image"]


def test_visual_camera_is_chosen_over_depth():
    sources = [
        "back_depth",
        "back_fisheye_image",
        "frontleft_fisheye_image",
        "frontright_depth",
    ]
    assert prefer_visual_source(sources) == "frontleft_fisheye_image"
