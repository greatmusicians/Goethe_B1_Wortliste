# coding=utf-8

import os
import sys
import shutil
import pytesseract
from PIL import Image


class Word:
    def __init__(self, img: Image.Image, source: str):
        self.img = img
        self.w = self.img.size[0]  # width
        self.h = self.img.size[1]  # height
        self.source = source
        self.left_width = find_word_spliter(img)

    def set_source(self, source: str):
        self.source = source

    def left_blank_percent(self) -> int:
        return round(get_margin_left(self.img) * 100 / self.w)

    def right_blank_percent(self) -> int:
        return round(get_margin_right(self.img) * 100 / self.w)

    def left(self) -> Image.Image:
        left = self.img.crop((0, 0, self.left_width, self.h))
        m = get_margin(left)
        if m[0] + m[2] >= left.size[0] or m[1] + m[3] >= left.size[1]:
            return left
        return left.crop((m[0], m[1], left.size[0] - m[2], left.size[1] - m[3]))

    def right(self) -> Image.Image:
        right = self.img.crop((self.left_width, 0, self.w, self.h))
        m = get_margin(right)
        if m[0] + m[2] >= right.size[0] or m[1] + m[3] >= right.size[1]:
            return right
        return right.crop((m[0], m[1], right.size[0] - m[2], right.size[1] - m[3]))

    # 对左半部分进行OCR文字识别，单词
    def left_text(self) -> str:
        return (
            str(pytesseract.image_to_string(image=self.left(), lang="deu"))
            .replace("\n", " ")
            .replace("  ", " ")
            .strip()
        )

    # 对右半部分进行OCR文字识别，例句
    def right_text(self) -> str:
        text = (
            str(pytesseract.image_to_string(image=self.right(), lang="deu"))
            .replace("\n", " ")
            .replace("  ", " ")
            .strip()
        )
        for i in range(9):
            text = text.replace(f" {i}. ", f"\n{i}. ")
        return text

    def add_margin(self, img: Image.Image) -> Image.Image:
        img_new = Image.new("RGB", (img.size[0] + 40, img.size[1] + 40), "white")
        img_new.paste(img, (20, 20))
        return img_new

    def save(self, filename: str) -> str:
        self.add_margin(self.img).save(filename)
        return filename

    def save_left(self, filename: str) -> str:
        self.add_margin(self.left()).save(filename)
        return filename


def is_blank(img: Image.Image) -> bool:
    extrema = img.convert("L").getextrema()
    return extrema[0] == extrema[1]


def is_blank_horizontal(img: Image.Image, start: int, end: int) -> bool:
    blank = is_blank(img.crop((0, start, img.size[0], end)))
    if blank:
        return True
    # 大于600个宽度的，允许进一步判断
    if img.size[0] < 600:
        return False
    # 允许有1个黑点，也按照空白计算，不然有一页会出问题
    dark_count = 0
    while start < end:
        for i in range(img.width):
            r, g, b = img.getpixel((i, start))
            if r < 200 and g < 200 and b < 200:
                dark_count += 1
        start += 1
    return dark_count < 2


def is_blank_vertical(img: Image.Image, start: int, end: int) -> bool:
    return is_blank(img.crop((start, 0, end, img.size[1])))


def get_margin(img: Image.Image) -> tuple[int, int, int, int]:
    return (
        get_margin_left(img),
        get_margin_upper(img),
        get_margin_right(img),
        get_margin_lower(img),
    )


def get_margin_left(img: Image.Image) -> int:
    w = img.size[0]
    left = 0
    while left < w and is_blank_vertical(img, 0, left + 1):
        left += 1
    return left


def get_margin_right(img: Image.Image) -> int:
    w = img.size[0]
    right = w
    while right >= 0 and is_blank_vertical(img, right - 1, w):
        right -= 1
    return w - right


def get_margin_upper(img: Image.Image) -> int:
    h = img.size[1]
    upper = 0
    while upper < h and is_blank_horizontal(img, 0, upper + 1):
        upper += 1
    return upper


def get_margin_lower(img: Image.Image) -> int:
    h = img.size[1]
    lower = h
    while lower >= 0 and is_blank_horizontal(img, lower - 1, h):
        lower -= 1
    return h - lower


def is_end_of_word(img: Image.Image, pos: int) -> bool:
    if pos < 0 or pos >= img.size[1]:
        return True

    # 如果不是空行，说明不是结束
    if not is_blank_horizontal(img, pos, pos + 1):
        return False

    # 第28页很特殊，单词部分没对齐，只有例句部分有大空白

    # 第一种，整行的下面有大空白
    offset = 1
    while pos + offset < img.size[1] and is_blank(
        img.crop((0, pos, img.size[0], pos + offset))
    ):
        offset += 1
    # 超过20像素高度的空白，或者直到边界都是空白
    is_end = offset > 20 or pos + offset == img.size[1]
    if is_end:
        return True

    # 第二种，需要同时满足：1，左半部分的上面有大空白；2，右半部分的下面有大空白
    offset_left_upper = 1
    while pos - offset_left_upper > 0 and is_blank(
        img.crop((0, pos - offset_left_upper, round(img.size[0] * 0.3), pos))
    ):
        offset_left_upper += 1
    left_upper = offset_left_upper > 20 or pos - offset_left_upper == 0

    offset_right_unter = 1
    while pos + offset_right_unter < img.size[1] and is_blank(
        img.crop((round(img.size[0] * 0.5), pos, img.size[0], pos + offset_right_unter))
    ):
        offset_right_unter += 1
    right_unter = offset_right_unter > 20 or pos + offset_right_unter == img.size[1]

    if left_upper and right_unter:
        return True

    # 第三种，需要同时满足：1，左半部分的上面有大空白；2，左半部分的下面没有大空白
    offset_left_unter = 1
    while pos + offset_left_unter < img.size[1] and is_blank(
        img.crop((round(img.size[0] * 0.5), pos, img.size[0], pos + offset_left_unter))
    ):
        offset_left_unter += 1
    left_unter = offset_left_unter < 10

    if left_upper and left_unter:
        return True

    return False


def get_word(img: Image.Image, start: int) -> tuple[Word, int]:
    if start < 0 or start >= img.size[1]:
        return None, 0

    # 忽略最开始的空白行
    while start < img.size[1]:
        if is_blank_horizontal(img, start, start + 1):
            start += 1
        else:
            break

    # 至少要有一行不是空白
    if start >= img.size[1] or is_blank_horizontal(img, start, start + 1):
        return None, 0

    end = start + 1
    while end < img.size[1] and not is_end_of_word(img, end):
        end += 1

    return Word(img.crop((0, start, img.size[0], end)), ""), end


def find_column_spliter(img: Image.Image) -> int:
    # 就在横向的700-1000之间，根据纵向的500-1000范围判断
    img = img.convert("L")
    pos = 700
    while pos < 1000:
        dark_count = 0
        for i in range(500):
            if img.getpixel((pos, 500 + i)) < 200:
                dark_count += 1
        if dark_count == 500:
            return pos
        pos += 1
    return -1


def find_word_spliter(img: Image.Image) -> int:
    # 就在横向的38%或264左右，有几个图片需要向右微调
    # 不知道为什么，在这里is_blank的方法不好用，会认为38%的位置并不是空白
    pos = round(img.size[0] * 0.38)
    while pos < round(img.size[0] * 0.45):
        dark_count = 0
        for j in range(img.size[1]):
            if dark_count > 10:
                break
            r, g, b = img.getpixel((pos, j))
            if r < 200 and g < 200 and b < 200:
                dark_count += 1
        if dark_count == 0:
            return pos
        pos += 1
    # 即使找不到，也返回38%
    return round(img.size[0] * 0.38)


def init_directory(directory: str) -> str:
    if os.path.exists(directory):
        shutil.rmtree(directory)
    # os.makedirs(directory, exist_ok=True)
    os.makedirs(directory)
    return directory


def load_images(directory: str) -> list[Image.Image]:
    dirs = os.listdir(directory)
    dirs.sort()
    img_list: list[Image.Image] = []
    for f in dirs:
        if f.endswith(("jpg", "png")):
            img_list.append(Image.open(os.path.join(directory, f)))
    return img_list


def get_max_text_width(directory: str) -> int:
    max_width = 0
    img_list = load_images(directory)
    for img in img_list:
        m_left, m_right = get_margin_left(img), get_margin_right(img)
        if img.size[0] - m_left - m_right > max_width:
            max_width = img.size[0] - m_left - m_right
    print("max_width", max_width)
    return max_width


def split_page():
    print("遍历所有页面，获取所有栏的图片")
    page_list = load_images("./Goethe-Zertifikat_B1_Wortliste.pdf_images")
    columns: list[Image.Image] = []
    for i in range(len(page_list)):
        img = page_list[i]
        pos_spliter = find_column_spliter(img)
        if pos_spliter < 0:
            print(i + 1)
            print("cannot find spliter")
        left = img.crop((70, 210, pos_spliter - 5, 2200))
        right = img.crop((pos_spliter + 5, 210, img.size[0] - 50, 2200))
        img.close()
        columns.append(left)
        columns.append(right)

    output_dir = init_directory("split_page")
    open(f"{output_dir}/hidden.txt", "w").close()
    for i in range(len(columns)):
        # print(i + 1)
        columns[i].save(f"{output_dir}/{i+1:0>3}.png")


def column_margin_test():
    print("切割边界，检查能够正确识别边界")
    columns = load_images("split_page")
    output_dir = init_directory("test_column_margin")
    open(f"{output_dir}/hidden.txt", "w").close()
    for i in range(len(columns)):
        c = columns[i]
        m = get_margin(c)
        img_new = c.crop((m[0], m[1], c.size[0] - m[2], c.size[1] - m[3]))
        img_new.save(f"{output_dir}/{i+1:0>3}.png")


def align_left():
    print("将所有栏文字左对齐，切掉右侧边界")
    max_width = get_max_text_width("split_page")
    columns = load_images("split_page")
    for i in range(len(columns)):
        c = columns[i]
        m_left = get_margin_left(c)
        img = Image.new("RGB", (max_width, c.size[1]), "white")
        img.paste(c.crop((m_left, 0, max_width + m_left, c.size[1])), (0, 0))
        columns[i] = img

    output_dir = init_directory("align_left")
    open(f"{output_dir}/hidden.txt", "w").close()
    for i in range(len(columns)):
        # print(i + 1)
        columns[i].save(f"{output_dir}/{i+1:0>3}.png")


def word_spliter_test():
    columns = load_images("align_left")
    output_dir = init_directory("word_spliter_test")
    open(f"{output_dir}/hidden.txt", "w").close()
    for i in range(len(columns)):
        c = columns[i]
        left_width = find_word_spliter(c)
        print("left_width", left_width)
        if left_width > 0:
            for j in range(c.size[1]):
                c.putpixel((left_width, j), (0, 0, 0))
        print("save", f"{output_dir}/{i+1:0>3}.png")
        c.save(f"{output_dir}/{i+1:0>3}.png")


def extract_word_test(filename: str, max_width: int, output_dir: str):
    c = Image.open(filename)
    word_list: list[Word] = []
    start = 0
    while start < c.size[1]:
        word, end = get_word(c, start)
        if word != None:
            start = end
            # 说明是空行
            if word.right_blank_percent() > 70:
                continue
            # > 35，说明从属于上一个单词
            # > 10，说明是上一个单词的衍生词
            if word.left_blank_percent() > 35 and len(word_list) > 0:
                last = word_list[len(word_list) - 1]
                img = Image.new("RGB", (max_width, last.h + word.h + 10), "white")
                img.paste(last.img, (0, 0))
                img.paste(word.img, (0, last.h + 10))
                word_list[len(word_list) - 1] = Word(img, "")
                print("word数量", len(word_list))
            else:
                word_list.append(word)
                print("word数量", len(word_list))
        else:
            break

    output_dir = init_directory(output_dir)
    open(f"{output_dir}/hidden.txt", "w").close()
    mdout = open("extract_word_test.md", "w")
    for i in range(len(word_list)):
        # print(i + 1)
        w = word_list[i]
        f = w.save(f"{output_dir}/{w.source:0>3}_{i+1:0>4}.png")
        f_left = w.save_left(f"{output_dir}/{i+1:0>4}_left.png")
        mdout.write(f"# {i+1:0>4}\n")
        mdout.write(f'<img class="img" src="{f}" />')
        mdout.write(f'<img class="img" src="{f_left}" />\n')
    mdout.close()


def extract_word_test_1(filename: str):
    c = Image.open(filename)
    start = 0
    while start < c.size[1]:
        dark_count = 0
        for i in range(c.width):
            r, g, b = c.getpixel((i, start))
            if r < 200 and g < 200 and b < 200:
                dark_count += 1
        if dark_count > 0 and dark_count < 2:
            print("dark_count", dark_count)
        if dark_count < 2:
            for i in range(c.width):
                c.putpixel((i, start), (0, 0, 0))
        start += 1
    c.save("extract_word_test_1.png")


def extract_word():
    print("截取所有单词")
    max_width = get_max_text_width("split_page")
    columns = load_images("align_left")
    word_list: list[Word] = []
    for i in range(len(columns)):
        c = columns[i]
        start = 0
        while start < c.size[1]:
            word, end = get_word(c, start)
            if word != None:
                start = end
                word.set_source(f"{i+1}")
                # 说明是空行
                if word.right_blank_percent() > 70:
                    continue
                # > 35，说明从属于上一个单词
                # > 10，说明是上一个单词的衍生词
                if word.left_blank_percent() > 35:
                    last = word_list[len(word_list) - 1]
                    img = Image.new("RGB", (max_width, last.h + word.h + 10), "white")
                    img.paste(last.img, (0, 0))
                    img.paste(word.img, (0, last.h + 10))
                    word_list[len(word_list) - 1] = Word(img, f"{i+1}")
                else:
                    word_list.append(word)
            else:
                break
    print("word数量", len(word_list))

    output_dir = init_directory("data")
    open(f"{output_dir}/hidden.txt", "w").close()
    md1 = open("extract_word.md", "w")
    md2 = open("Goethe_B1_Wortliste.md", "w")
    for i in range(len(word_list)):
        # print(i + 1)
        w = word_list[i]
        f = w.save(f"{output_dir}/{w.source:0>3}_{i+1:0>4}.png")
        f_left = w.save_left(f"{output_dir}/{w.source:0>3}_{i+1:0>4}_left.png")
        left_text, right_text = w.left_text(), w.right_text()
        md1.write(f"# {w.source:0>3}_{i+1:0>4}\n")
        md1.write(f'<img class="img" src="{f}" />')
        md1.write(f'<img class="img" src="{f_left}" />\n')
        md2.write(f'<div class="QSA"><Q><img src="{f_left}" />\n{left_text}</Q>')
        md2.write(f'<A><img src="{f}" />\n{right_text}</A></div>\n')
        md2.write('<div class="Wort">')
        md2.write(f"<W1>{left_text}</W1><W2></W2><W3></W3><W4></W4><Notiz>\n")
        md2.write(f"{right_text}</Notiz></div>\n\n")
    md1.close()
    md2.close()


if __name__ == "__main__":
    if sys.argv[1] == "split_page":
        split_page()
    if sys.argv[1] == "column_margin_test":
        column_margin_test()
    if sys.argv[1] == "align_left":
        align_left()
    if sys.argv[1] == "word_spliter_test":
        word_spliter_test()
    if sys.argv[1] == "extract_word":
        extract_word()
    if sys.argv[1] == "extract_word_test":
        extract_word_test(sys.argv[2], int(sys.argv[3]), sys.argv[4])
    if sys.argv[1] == "extract_word_test_1":
        extract_word_test_1(sys.argv[2])
