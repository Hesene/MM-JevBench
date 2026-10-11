from convert.convert_multi import parse_options


def test_parse_standard_options() -> None:
    question, options = parse_options("题干内容\nA. 甲\nB. 乙\nC. 丙\nD. 丁")
    assert question == "题干内容"
    assert options == [("A", "甲"), ("B", "乙"), ("C", "丙"), ("D", "丁")]


def test_question_prefix_that_looks_like_option_is_not_consumed() -> None:
    content = "A. B两地相距50km，函数图像是哪一个？\nA. [IMAGE_1]\nB. [IMAGE_2]\nC. [IMAGE_3]\nD. [IMAGE_4]"
    question, options = parse_options(content)
    assert question == "A. B两地相距50km，函数图像是哪一个？"
    assert options == [
        ("A", "[IMAGE_1]"),
        ("B", "[IMAGE_2]"),
        ("C", "[IMAGE_3]"),
        ("D", "[IMAGE_4]"),
    ]


def test_lowercase_option_marker_is_normalized() -> None:
    question, options = parse_options("题干\nA. 甲\nB. 乙\nc. 丙\nD. 丁")
    assert question == "题干"
    assert options == [("A", "甲"), ("B", "乙"), ("C", "丙"), ("D", "丁")]
